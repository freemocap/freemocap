"""Bind completed numerical stages to the point streams and models being published."""

import numpy as np

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.reconstruction.recording_fit import RecordingFitInputs
from freemocap.core.recording.result_processing.input_signatures import definition_signature
from freemocap.core.recording.result_processing.observation_inputs import (
    ObservationRecordingRequest,
)
from freemocap.core.recording.data_descriptors.recording_descriptor import StageCheckpoint
from freemocap.core.recording.result_processing.saved_reconstruction import (
    SavedPointSeries,
)
from freemocap.core.types.channel_kind import ChannelKind


def reconstruction_checkpoints(
    *, request: ObservationRecordingRequest, timestamps_s: tuple[float, ...]
) -> tuple[StageCheckpoint, ...]:
    if not request.reconstructions:
        return ()
    models = {model.model_id: model for model in request.models}
    points: dict[str, str] = {}
    raw_points: dict[str, str] = {}
    fits: dict[str, str] = {}
    reconstruction: dict[str, str] = {}
    for item in sorted(
        request.reconstructions, key=lambda item: item.definition.model_id
    ):
        model = models[item.definition.model_id]
        candidates = tuple(
            series
            for series in request.spatial_series
            if series.definition.source == item.definition.tracker
            and series.definition.reference == item.reference
            and series.definition.kind == item.definition.point_kind
        )
        if len(candidates) != 1:
            raise ValueError(
                "Completion requires exactly one matching published reconstruction input stream"
            )
        series = candidates[0]
        if item.definition.point_kind == ChannelKind.KEYPOINTS_3D:
            raw = tuple(series for series in request.spatial_series
                if series.definition.source == item.definition.tracker
                and series.definition.reference == item.reference
                and series.definition.kind == ChannelKind.RAW_KEYPOINTS_3D)
            if len(raw) != 1 or request.filtering is None:
                raise ValueError("Filtered reconstruction requires raw points and a filtering report")
            if raw[0].definition.names != series.definition.names or not np.array_equal(
                np.isfinite(raw[0].values), np.isfinite(series.values),
            ):
                raise ValueError("Filtered points must preserve raw point names and missing observations")
            raw_points[model.model_id] = SavedPointSeries(
                channel=raw[0].definition.to_channel(), frames=request.group.frame_numbers,
                timestamps_s=timestamps_s, values=raw[0].values,
            ).signature()
        expected = RecordingFitInputs.from_points(
            names=series.definition.names, values=series.values, model=model
        )
        if item.result.fit_inputs != expected:
            raise ValueError(
                "Published points or model differ from the completed scale-fit inputs"
            )
        points[model.model_id] = SavedPointSeries(
            channel=series.definition.to_channel(),
            frames=request.group.frame_numbers,
            timestamps_s=timestamps_s,
            values=series.values,
        ).signature()
        fits[model.model_id] = definition_signature(item.to_scale_fit())
        reconstruction[model.model_id] = definition_signature(
            dict(
                fit=fits[model.model_id],
                points=points[model.model_id],
                compute_center_of_mass=item.result.compute_center_of_mass,
            )
        )
    # Versions cover the numerical stage and its input-selection semantics.
    signatures = {
        ProcessingStage.FILTERING: definition_signature(
            dict(version=2, raw_points=raw_points, points=points, filtering=request.filtering)
        ),
        ProcessingStage.SCALE_FIT: definition_signature(
            dict(version=1, points=points, fits=fits)
        ),
        ProcessingStage.RECONSTRUCTION: definition_signature(
            dict(version=1, models=reconstruction)
        ),
    }
    if all(item.result.compute_center_of_mass for item in request.reconstructions):
        signatures[ProcessingStage.BIOMECHANICS] = definition_signature(
            dict(version=1, models=reconstruction)
        )
    return tuple(
        StageCheckpoint(
            sensor_group=request.group.name, stage=stage, signature=signature
        )
        for stage, signature in signatures.items()
    )
