"""Load an explicit saved point stream, scientific model and fit without media access."""

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import NDArray
import pyarrow.compute as pc
import pyarrow.parquet as pq

from freemocap.core.reconstruction.recording_reconstruction import (
    RecordingReconstructionInput,
)
from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.recording.result_processing.input_signatures import (
    ReconstructionInputSignatures,
    definition_signature,
    point_array_signature,
)
from freemocap.core.recording.sample_encoding.arrow_schema import SampleValidator
from freemocap.core.recording.data_descriptors.recording_descriptor import Channel, RecordingMetadata
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.recording.data_descriptors.scale_fit import RecordingScaleFit
from freemocap.core.recording.parquet_storage.parquet_writer import recording_write_lock
from freemocap.core.recording.data_descriptors.sample_conventions import SampleComponent
from freemocap.core.recording.sample_encoding.spatial_points import SpatialReference
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.system.recording_structure.recording_structure import RecordingStructure


class SavedPointPolicy(StrEnum):
    IDENTITY = "identity"


@dataclass(frozen=True, slots=True)
class SavedReconstructionRequest:
    structure: RecordingStructure
    run_id: int
    sensor_group: str
    point_source: str
    model_id: str
    point_policy: SavedPointPolicy
    compute_center_of_mass: bool


@dataclass(frozen=True, slots=True)
class SavedPointSeries:
    channel: Channel
    frames: tuple[int, ...]
    timestamps_s: tuple[float, ...]
    values: NDArray[np.float64]

    def signature(self) -> str:
        return definition_signature(
            dict(
                channel=self.channel,
                frames=self.frames,
                timestamps_s=self.timestamps_s,
                values=point_array_signature(self.values),
            )
        )


@dataclass(frozen=True, slots=True)
class SavedReconstruction:
    points: SavedPointSeries
    numerical_input: RecordingReconstructionInput
    fit: RecordingScaleFit
    signatures: ReconstructionInputSignatures


def read_saved_reconstruction(
    request: SavedReconstructionRequest,
) -> SavedReconstruction:
    """Identity policy explicitly consumes RAW_KEYPOINTS_3D; no filter or refit is inferred.

    The fit must describe these exact numeric inputs and scientific model. Returned fingerprints
    identify the selection; worker-level completion reuse requires stage-planner validation.
    """
    if request.point_policy != SavedPointPolicy.IDENTITY:
        raise ValueError("Unsupported saved-point processing policy")
    with recording_write_lock(structure=request.structure):
        metadata = read_metadata(path=request.structure.data_parquet_path)
        if metadata.recording_id != request.structure.recording_name:
            raise ValueError("Recording identity does not match its directory")
        run = metadata.runs[request.run_id]
        model = run.models[request.model_id]
        if model.detector_type != request.point_source:
            raise ValueError(
                "Selected point source does not match the saved model's tracker"
            )
        channels = tuple(
            channel
            for channel in run.channels
            if channel.sensor_group == request.sensor_group
            and channel.source == request.point_source
            and channel.kind == ChannelKind.RAW_KEYPOINTS_3D
        )
        if len(channels) != 1:
            raise ValueError(
                "Saved reconstruction requires exactly one selected raw point channel"
            )
        channel = channels[0]
        reference = SpatialReference.model_validate(
            run.reference_frames[channel.reference_frame]
        )
        if channel.components != {
            component: reference.units
            for component in (SampleComponent.X, SampleComponent.Y, SampleComponent.Z)
        }:
            raise ValueError(
                "Saved reconstruction requires spatial xyz components in declared units"
            )
        fits = tuple(
            fit
            for fit in run.scale_fits
            if fit.source == request.model_id
            and fit.sensor_group == request.sensor_group
        )
        if len(fits) != 1:
            raise ValueError(
                "Saved reconstruction requires one explicit fit record, including an absent fit"
            )
        fit = fits[0]
        if (
            fit.reference_frame != channel.reference_frame
            or fit.units != reference.units
        ):
            raise ValueError(
                "Saved points and fit must use the same reference and spatial units"
            )
        points = _read_points(request=request, metadata=metadata, channel=channel)
        numerical_input = RecordingReconstructionInput(
            bundles=(model.to_bundle(),),
            keypoint_names=channel.names,
            keypoints_3d=points.values,
            compute_center_of_mass=request.compute_center_of_mass,
            timing=PosthocTimingReport(),
        )
        if fit.inputs != numerical_input.fit_inputs(numerical_input.bundles[0]):
            raise ValueError(
                "Saved scale fit inputs changed; rerun recording-wide fitting"
            )
        point_signature = points.signature()
        model_signature = definition_signature(model)
        fit_signature = definition_signature(fit)
        return SavedReconstruction(
            points=points,
            numerical_input=numerical_input,
            fit=fit,
            signatures=ReconstructionInputSignatures(
                points=point_signature,
                model=model_signature,
                fit=fit_signature,
                reconstruction=definition_signature(
                    dict(
                        points=point_signature,
                        model=model_signature,
                        fit=fit_signature,
                        point_policy=request.point_policy,
                        compute_center_of_mass=request.compute_center_of_mass,
                    )
                ),
            ),
        )


def _read_points(
    *,
    request: SavedReconstructionRequest,
    metadata: RecordingMetadata,
    channel: Channel,
) -> SavedPointSeries:
    run = metadata.runs[request.run_id]
    count = run.sensor_groups[request.sensor_group].sample_count
    if count < 1:
        raise ValueError("Saved reconstruction requires a nonempty point stream")
    selected_metadata = metadata.model_copy(
        update={
            "runs": {request.run_id: run.model_copy(update={"channels": (channel,)})}
        }
    )
    validator = SampleValidator(metadata=selected_metadata)
    values = np.full((count, len(channel.names), 3), np.nan, dtype=np.float64)
    frame_indices: dict[int, int] = {}
    timestamps: dict[int, float] = {}
    names = {name: index for index, name in enumerate(channel.names)}
    components = {SampleComponent.X: 0, SampleComponent.Y: 1, SampleComponent.Z: 2}
    with pq.ParquetFile(request.structure.data_parquet_path) as parquet:
        for batch in parquet.iter_batches(batch_size=65536):
            mask = pc.and_(
                pc.equal(batch.column("run_id"), request.run_id),
                pc.equal(batch.column("sensor_group"), request.sensor_group),
            )
            mask = pc.and_(mask, pc.equal(batch.column("source"), channel.source))
            mask = pc.and_(mask, pc.equal(batch.column("channel"), channel.kind))
            mask = pc.and_(
                mask, pc.equal(batch.column("reference_frame"), channel.reference_frame)
            )
            selected = batch.filter(mask).replace_schema_metadata(None)
            if not selected.num_rows:
                continue
            validator.accept(batch=selected)
            columns = selected.to_pydict()
            for frame, timestamp, name, component, value in zip(
                columns["frame_number"],
                columns["timestamp_s"],
                columns["name"],
                columns["component"],
                columns["value"],
                strict=True,
            ):
                if frame not in frame_indices:
                    if len(frame_indices) == count:
                        raise ValueError(
                            "Point stream exceeds the declared frame count"
                        )
                    frame_indices[frame] = len(frame_indices)
                    timestamps[frame] = timestamp
                elif timestamps[frame] != timestamp:
                    raise ValueError("Point components disagree on the frame timestamp")
                values[frame_indices[frame], names[name], components[component]] = (
                    np.nan if value is None else value
                )
    validator.finish()
    frames = tuple(sorted(frame_indices))
    if len(frames) != count:
        raise ValueError("Point stream does not cover the declared frame grid")
    ordered = values[[frame_indices[frame] for frame in frames]]
    ordered.flags.writeable = False
    return SavedPointSeries(
        channel=channel,
        frames=frames,
        timestamps_s=tuple(timestamps[frame] for frame in frames),
        values=ordered,
    )
