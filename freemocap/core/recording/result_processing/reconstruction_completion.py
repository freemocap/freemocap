"""Bind completed numerical stages to the point streams and models being published."""

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.reconstruction.recording_fit import RecordingFitInputs
from freemocap.core.recording.result_processing.input_signatures import definition_signature
from freemocap.core.recording.result_processing.observation_inputs import (
    ObservationRecordingRequest,
)
from freemocap.core.recording.data_descriptors.recording_descriptor import StageCheckpoint
from freemocap.core.recording.result_processing.saved_reconstruction import (
    SavedPointPolicy,
    SavedPointSeries,
)


def reconstruction_checkpoints(
    *, request: ObservationRecordingRequest, timestamps_s: tuple[float, ...]
) -> tuple[StageCheckpoint, ...]:
    if not request.reconstructions:
        return ()
    models = {model.model_id: model for model in request.models}
    points: dict[str, str] = {}
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
        )
        if len(candidates) != 1:
            raise ValueError(
                "Completion requires exactly one matching published reconstruction input stream"
            )
        series = candidates[0]
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
            dict(version=1, policy=SavedPointPolicy.IDENTITY, points=points)
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
