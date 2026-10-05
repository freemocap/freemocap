"""Provenance for observation and reconstruction publication boundaries."""

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.recording.data_descriptors.stage_provenance import StageProvenance
from freemocap.core.recording.data_descriptors.recording_descriptor import RunDescriptor
from freemocap.core.recording.result_processing.observation_inputs import ObservationRecordingRequest
from freemocap.core.recording.result_processing.provenance import stage_settings
from freemocap.core.recording.result_processing.input_signatures import definition_signature, point_array_signature

def observation_provenance(*, request: "ObservationRecordingRequest", run: "RunDescriptor",
                           timestamps_s: tuple[float, ...]) -> dict[ProcessingStage, StageProvenance]:
    context = request.provenance_context
    if context is None:
        return {}  # Historical/direct publications cannot invent execution provenance.
    stages = {channel.stage for channel in run.channels}
    stages.update(checkpoint.stage for checkpoint in run.checkpoints)
    if request.reuse_observations:
        stages.difference_update((ProcessingStage.TIMING, ProcessingStage.OBSERVATIONS))
    observation_content = []
    if ProcessingStage.OBSERVATIONS in stages:
        for frame in request.group.frames:
            observation_content.append({camera: definition_signature(dict(
                names=obs.to_keypoints().names, xyz=point_array_signature(obs.to_keypoints().xyz),
                visibility=point_array_signature(obs.to_keypoints().visibility))) for camera, obs in frame.items()})
    point_inputs = {series.definition.kind.value: dict(
        names=series.definition.names, values=point_array_signature(series.values)) for series in request.spatial_series}
    result = {}
    for stage in stages:
        sources = tuple(c.source for c in run.channels if c.stage == stage)
        if not sources:
            sources = tuple(item.definition.source_name for item in request.reconstructions)
        inputs = dict(timing=dict(frames=request.group.frame_numbers, timestamps_s=timestamps_s))
        if stage == ProcessingStage.OBSERVATIONS:
            inputs['observations'] = observation_content
        elif stage == ProcessingStage.TIMING:
            inputs['camera_timing'] = {name: source.definition for name, source in run.sources.items() if source.kind in ('camera', 'timing')}
        else:
            inputs.update(points=point_inputs, camera_geometry=run.camera_geometry,
                          models=run.models, scale_fits=run.scale_fits)
            if request.filtering is not None:
                inputs['filtering_report'] = request.filtering
        result[stage] = context.record(
            settings=stage_settings(stage, request.tracker.configuration, filtering=request.filtering),
            defaults=stage_settings(stage, request.provenance_defaults) if request.provenance_defaults is not None else None,
            inputs=inputs, sources=sources,
            limitations=('Tracker settings describe requested execution providers; actual runtime fallback is not exposed by this adapter.',)
                if stage == ProcessingStage.OBSERVATIONS else ())
    return result
