"""Load an explicit saved point stream, scientific model and fit without media access."""

from dataclasses import dataclass, field
from contextlib import nullcontext
from enum import StrEnum

from freemocap.core.reconstruction.posthoc_filtering import PosthocFilterReport

import numpy as np
from numpy.typing import NDArray

from freemocap.core.reconstruction.recording_reconstruction import (
    RecordingReconstructionInput,
)
from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.recording.result_processing.input_signatures import (
    ReconstructionInputSignatures,
    definition_signature,
    point_array_signature,
)
from freemocap.core.recording.data_descriptors.recording_descriptor import Channel, RecordingMetadata
from freemocap.core.recording.parquet_storage.recording_view import RecordingView, recording_view
from freemocap.core.recording.parquet_storage.channel_arrays import ChannelArrays, read_channel_arrays
from freemocap.core.recording.parquet_storage.channel_selection import ChannelSelection
from freemocap.core.recording.data_descriptors.scale_fit import RecordingScaleFit
from freemocap.core.recording.parquet_storage.parquet_writer import recording_write_lock
from freemocap.core.recording.data_descriptors.sample_conventions import SampleComponent
from freemocap.core.recording.sample_encoding.spatial_points import SpatialReference
from freemocap.core.recording.sample_encoding.reconstruction_samples import (
    ReconstructionSourceDefinition,
    model_source_name,
)
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.system.recording_structure.recording_structure import RecordingStructure


class SavedPointPolicy(StrEnum):
    IDENTITY = "identity"
    FILTERED = "filtered"

    @property
    def channel_kind(self) -> ChannelKind:
        return ChannelKind.RAW_KEYPOINTS_3D if self == SavedPointPolicy.IDENTITY else ChannelKind.KEYPOINTS_3D


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
    """Convenience access over shared channel arrays; values are never duplicated."""
    channel: Channel
    frames: tuple[int, ...]
    timestamps_s: tuple[float, ...]
    values: NDArray[np.float64]
    present: NDArray[np.bool_] | None = None
    channel_arrays: ChannelArrays = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Computed channels describe every declared cell, even when its value is NaN.
        # Broadcast the constant presence flag instead of allocating a full mask.
        presence = np.broadcast_to(np.array(True), self.values.shape) if self.present is None else self.present
        arrays = ChannelArrays(_channel_selection(self.channel), self.channel.names,
            tuple(self.channel.components), tuple(self.channel.components.values()),
            np.asarray(self.frames, dtype=np.int64), np.asarray(self.timestamps_s, dtype=np.float64), self.values, presence)
        object.__setattr__(self, 'present', presence)
        object.__setattr__(self, 'channel_arrays', arrays)

    @classmethod
    def from_arrays(cls, *, channel: Channel, arrays: ChannelArrays) -> "SavedPointSeries":
        # The assembler already owns axis arrays: keep those arrays as well as values.
        instance = object.__new__(cls)
        for name, value in (('channel', channel), ('frames', tuple(arrays.frames.tolist())),
                            ('timestamps_s', tuple(arrays.timestamps.tolist())), ('values', arrays.values),
                            ('present', arrays.present), ('channel_arrays', arrays)):
            object.__setattr__(instance, name, value)
        return instance

    def signature(self) -> str:
        return definition_signature(dict(channel=self.channel, frames=self.frames,
            timestamps_s=self.timestamps_s, values=point_array_signature(self.values)))


def _channel_selection(channel: Channel) -> ChannelSelection:
    return ChannelSelection(sensor_group=channel.sensor_group, source=channel.source,
                            reference_frame=channel.reference_frame, channel=str(channel.kind))


@dataclass(frozen=True, slots=True)
class SavedReconstruction:
    points: SavedPointSeries
    numerical_input: RecordingReconstructionInput
    fit: RecordingScaleFit
    signatures: ReconstructionInputSignatures


def read_saved_reconstruction(
    request: SavedReconstructionRequest,
    *, view: RecordingView | None = None,
) -> SavedReconstruction:
    """Load the explicitly selected raw or filtered input stream without filtering it again.

    The fit must describe these exact numeric inputs and scientific model. Returned fingerprints
    identify the selection; worker-level completion reuse requires stage-planner validation.
    """
    with recording_write_lock(structure=request.structure), (
        recording_view(request.structure.data_parquet_path) if view is None else nullcontext(view)
    ) as current_view:
        metadata = current_view.metadata
        if metadata.recording_id != request.structure.recording_name:
            raise ValueError("Recording identity does not match its directory")
        run = metadata.runs[request.run_id]
        model = run.models[request.model_id]
        reconstruction_source = ReconstructionSourceDefinition.model_validate(
            run.sources[model_source_name(request.model_id)].definition
        )
        if reconstruction_source.point_kind != request.point_policy.channel_kind:
            raise ValueError("Requested point policy differs from the saved reconstruction input channel")
        if reconstruction_source.model_id != request.model_id or reconstruction_source.tracker != request.point_source:
            raise ValueError(
                "Selected point source does not match the saved model's tracker"
            )
        channels = tuple(
            channel
            for channel in run.channels
            if channel.sensor_group == request.sensor_group
            and channel.source == request.point_source
            and channel.kind == request.point_policy.channel_kind
        )
        if len(channels) != 1:
            raise ValueError(
                "Saved reconstruction requires exactly one selected point channel"
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
            if fit.source == model_source_name(request.model_id)
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
        points = read_saved_channel(structure=request.structure, run_id=request.run_id,
            metadata=metadata, channel=channel, view=current_view)
        # Storage retains authored component order. Spatial geometry explicitly
        # requires XYZ, so gather once only when that order differs.
        spatial_components = (SampleComponent.X, SampleComponent.Y, SampleComponent.Z)
        component_names = tuple(channel.components)
        spatial_values = points.values if component_names == spatial_components else np.take(
            points.values, [component_names.index(component) for component in spatial_components], axis=-1)
        measured_support = None
        processing = run.processing.get(request.sensor_group, {}).get('filtering')
        if request.point_policy == SavedPointPolicy.FILTERED and processing is not None:
            report = PosthocFilterReport.model_validate(processing)
            if report.gap_filling is not None:
                measured_support = report.gap_filling.measured_support(spatial_values)
        numerical_input = RecordingReconstructionInput(
            bundles=(model.to_bundle(),),
            keypoint_names=channel.names,
            keypoints_3d=spatial_values,
            measured_support=measured_support,
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


def read_saved_channel(*, structure: RecordingStructure, run_id: int,
                       metadata: RecordingMetadata, channel: Channel,
                       view: RecordingView | None = None) -> SavedPointSeries:
    """Read a complete channel in authored order into owned read-only arrays.

    A caller-owned view shares one open file across related channel reads. The
    caller still holds the recording lock. Returned numerical storage survives
    view closure; the complete output is resident, while decoding is batched.
    """
    if view is None:
        with recording_view(structure.data_parquet_path) as current_view:
            return read_saved_channel(structure=structure, run_id=run_id,
                metadata=metadata, channel=channel, view=current_view)
    if metadata is not view.metadata and metadata != view.metadata:
        raise ValueError('Recording metadata changed before the channel read')
    if metadata.recording_id != structure.recording_name:
        raise ValueError('Recording identity does not match its directory')
    run = metadata.runs[run_id]
    if channel not in run.channels:
        raise ValueError('Saved channel is not declared in the selected run')
    if run.sensor_groups[channel.sensor_group].sample_count < 1:
        raise ValueError('Saved reconstruction requires a nonempty point stream')
    with read_channel_arrays(view, run_id, _channel_selection(channel), channel,
                             require_complete=True) as arrays:
        for array in (arrays.values, arrays.present, arrays.frames, arrays.timestamps):
            array.flags.writeable = False
        return SavedPointSeries.from_arrays(channel=channel, arrays=arrays)
