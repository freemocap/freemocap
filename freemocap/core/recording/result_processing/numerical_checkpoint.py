"""Save requested numerical stages against the exact recording snapshot read."""
from freemocap.core.recording.result_processing.run_save_session import RunSaveSession
from collections.abc import Callable
from concurrent.futures import CancelledError

from freemocap.core.pipeline.dataflow.saved_spatial_source import SavedSpatialSource
from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.pipeline.posthoc.stage_dependencies import dependency_closure, stage_dependencies
from freemocap.core.pipeline.posthoc.stage_execution_plan import StageExecutionPlan, retained_run
from freemocap.core.recording.parquet_storage.parquet_writer import recording_write_lock
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.core.recording.parquet_storage.checkpoint_publication import publish_checkpoint
from freemocap.core.recording.data_descriptors.recording_descriptor import RunDescriptor, StageCheckpoint
from freemocap.core.recording.data_descriptors.recording_model import RecordedModel
from freemocap.core.recording.data_descriptors.scale_fit import RecordingScaleFit
from freemocap.core.recording.data_descriptors.stage_provenance import stage_provenance, set_stage_provenance
from freemocap.core.recording.result_processing.input_signatures import definition_signature
from freemocap.core.recording.result_processing.provenance import ProvenanceContext, stage_settings
from freemocap.core.recording.result_processing.saved_reconstruction import SavedPointSeries
from freemocap.core.recording.sample_encoding.channel_series import ChannelSeries, SeriesSampling
from freemocap.core.recording.sample_encoding.reconstruction_samples import ReconstructionRecording, ReconstructionSourceDefinition
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.types.channel_kind import ChannelKind


def save_numerical_checkpoint(*, source: SavedSpatialSource, config: PosthocMocapPipelineConfig,
                              numerical, filtering, fits: dict, results: dict,
                              run_session: RunSaveSession | None = None, cancelled: Callable[[], bool] = lambda: False):
    start, stop = ProcessingStage(config.start_stage), ProcessingStage(config.stop_stage)
    order = (ProcessingStage.FILTERING, ProcessingStage.SCALE_FIT, ProcessingStage.RECONSTRUCTION)
    executed = order[order.index(start):order.index(stop) + 1]
    if stop == ProcessingStage.RECONSTRUCTION:
        executed += (ProcessingStage.BIOMECHANICS,)
    invalidated = tuple(s for s in ProcessingStage if start in dependency_closure(stages={s}, dependencies=stage_dependencies()))
    if run_session is None:
        run_session = RunSaveSession.resolve(structure=source.structure, source_run_id=source.run_id, mode=config.run_save_mode)
    target_run_id = run_session.target_run_id
    plan = StageExecutionPlan(source.run_id, target_run_id, (source.group,), executed, invalidated)
    base = source.metadata.runs[source.run_id]
    retained = retained_run(base=base, plan=plan)
    data = retained.model_dump()
    series = []
    points = source.points
    prepared = SavedPointSeries(channel=points.channel.model_copy(update={'kind': ChannelKind.KEYPOINTS_3D,
        'stage': ProcessingStage.FILTERING}), frames=points.frames, timestamps_s=points.timestamps_s, values=numerical.keypoints_3d)
    if start == ProcessingStage.FILTERING:
        series.append(ChannelSeries(channel=prepared.channel, values=prepared.values))
        settings = dict(data['processing'].get(source.group, {}))
        settings['filtering'] = filtering.model_dump(mode='json')
        data['processing'][source.group] = settings
    fit_records, reconstructions = [], []
    if ProcessingStage.SCALE_FIT in executed or ProcessingStage.RECONSTRUCTION in executed:
        if set(fits) != {b.model_id for b in numerical.bundles}:
            raise ValueError('Scale fits must cover every requested model')
        for bundle in numerical.bundles:
            fit = fits[bundle.model_id]
            if fit.inputs != numerical.fit_inputs(bundle):
                raise ValueError('Scale fit inputs changed before saving')
            definition = ReconstructionSourceDefinition.from_bundle(bundle, tracker_source=points.channel.source,
                                                                     point_kind=ChannelKind.KEYPOINTS_3D)
            data['models'][bundle.model_id] = RecordedModel.from_bundle(bundle)
            data['sources'][definition.source_name] = definition.to_source()
            fit_records.append(RecordingScaleFit(sensor_group=source.group, source=definition.source_name,
                reference_frame=source.reference.name, units=source.reference.units, inputs=fit.inputs, fit=fit.fit))
            if stop == ProcessingStage.RECONSTRUCTION:
                reconstruction = ReconstructionRecording(sensor_group=source.group, reference=source.reference,
                    definition=definition, result=results[bundle.model_id])
                reconstructions.append(reconstruction)
                series.extend(reconstruction.series())
                data['reference_frames'].update(reconstruction.reference_frames())
    if ProcessingStage.SCALE_FIT in executed:
        data['scale_fits'] = (*retained.scale_fits, *fit_records)
    data['channels'] = (*retained.channels, *(s.channel for s in series))
    point_signature = prepared.signature()
    point_signatures = {b.model_id: point_signature for b in numerical.bundles}
    fit_signatures = {b.model_id: definition_signature(f) for b, f in zip(numerical.bundles, fit_records, strict=False)}
    model_signatures = {r.definition.model_id: definition_signature(dict(fit=fit_signatures[r.definition.model_id],
        points=point_signature, compute_center_of_mass=r.result.compute_center_of_mass)) for r in reconstructions}
    signatures = {
        ProcessingStage.FILTERING: definition_signature(dict(version=2,
            raw_points={b.model_id: points.signature() for b in numerical.bundles}, points=point_signatures, filtering=filtering)),
        ProcessingStage.SCALE_FIT: definition_signature(dict(version=1, points=point_signatures, fits=fit_signatures)),
        ProcessingStage.RECONSTRUCTION: definition_signature(dict(version=1, models=model_signatures)),
        ProcessingStage.BIOMECHANICS: definition_signature(dict(version=1, models=model_signatures)),
    }
    data['checkpoints'] = (*retained.checkpoints, *(StageCheckpoint(sensor_group=source.group, stage=s,
                                                                  signature=signatures[s]) for s in executed))
    entries = dict(stage_provenance(retained.processing, source.group).stages)
    provenance = ProvenanceContext.create()
    defaults = PosthocMocapPipelineConfig().model_dump(mode='json')
    for stage in executed:
        entries[stage] = provenance.record(settings=stage_settings(stage, config.model_dump(mode='json'), filtering=filtering),
            defaults=stage_settings(stage, defaults), inputs=dict(points=points.signature(), prepared_points=point_signature,
                models=base.models, fits=fit_signatures, filtering_report=filtering),
            sources=(points.channel.source,) if stage == ProcessingStage.FILTERING else tuple(f.source for f in fit_records),
            base_run_id=source.run_id, base_descriptor=base)
    data['processing'] = set_stage_provenance(data['processing'], source.group, entries)
    result = RunDescriptor.model_validate(data)
    sampling = SeriesSampling(points.frames, points.timestamps_s, target_run_id)
    with recording_write_lock(structure=source.structure):
        with recording_view(source.structure.data_parquet_path) as view:
            if view.revision != source.revision or view.metadata != source.metadata:
                raise ValueError('Recording changed after loading saved inputs; rerun this request')
        if cancelled():
            raise CancelledError('Cancelled before saving numerical results')
        def batches():
            for item in series:
                for batch in item.batches(sampling):
                    if cancelled():
                        raise CancelledError('Cancelled while saving numerical results')
                    yield batch
        if run_session:
            run_session.check(source.metadata)
        published = publish_checkpoint(structure=source.structure, metadata=source.metadata, plan=plan, result=result,
                                  computed_batches=batches(), cancelled=cancelled)

        return run_session.accept(published) if run_session else published
