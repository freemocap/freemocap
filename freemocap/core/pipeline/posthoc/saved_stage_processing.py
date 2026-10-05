"""Resume numerical processing from validated canonical recording channels."""

from concurrent.futures import CancelledError
from dataclasses import replace
from collections.abc import Callable
from pathlib import Path

import numpy as np

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.pipeline.posthoc.task_progress_reporter import TaskProgressReporter
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.pipeline.posthoc.stage_dependencies import dependency_closure, stage_dependencies
from freemocap.core.pipeline.posthoc.stage_execution_plan import StageExecutionPlan, retained_run
from freemocap.core.reconstruction.posthoc_filtering import PosthocFilterReport, prepare_recording_points
from freemocap.core.reconstruction.posthoc_reconstruction import reconstruct_skeletons_for_recording, reconstruct_skeletons_with_fits
from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.reconstruction.recording_fit import FittedRecordingScale
from freemocap.core.reconstruction.recording_reconstruction import RecordingReconstructionInput
from freemocap.core.recording.data_descriptors.recording_descriptor import RunDescriptor, StageCheckpoint
from freemocap.core.recording.parquet_storage.checkpoint_publication import publish_checkpoint
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.recording.parquet_storage.parquet_writer import recording_write_lock
from freemocap.core.recording.result_processing.input_signatures import definition_signature
from freemocap.core.recording.result_processing.saved_reconstruction import SavedPointSeries, read_saved_channel
from freemocap.core.recording.sample_encoding.channel_series import ChannelSeries, SeriesSampling
from freemocap.core.recording.sample_encoding.reconstruction_samples import ReconstructionRecording, ReconstructionSourceDefinition, model_source_name
from freemocap.core.recording.sample_encoding.spatial_points import SpatialReference
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.core.recording.result_processing.provenance import ProvenanceContext, stage_settings
from freemocap.core.recording.data_descriptors.stage_provenance import stage_provenance, set_stage_provenance


RESUME_STAGES = ('observations', 'triangulation', 'filtering', 'scale_fit', 'reconstruction', 'skeleton_fit')


def recording_structure(path: str) -> RecordingStructure:
    folder = Path(path).expanduser()
    return RecordingStructure(base_directory=folder.parent, recording_name=folder.name)


def select_group(run: RunDescriptor, requested: str | None) -> str:
    groups = {c.sensor_group for c in run.channels if c.kind in
              (ChannelKind.OVERLAY_2D, ChannelKind.RAW_KEYPOINTS_3D, ChannelKind.KEYPOINTS_3D)}
    if requested is not None:
        if requested not in groups:
            raise ValueError('The selected sensor group has no saved mocap inputs')
        return requested
    if len(groups) != 1:
        raise ValueError('Select a sensor group for reprocessing')
    return next(iter(groups))


def inspect_saved_stages(path: str) -> dict:
    """Descriptor inventory; readers validate full component grids before reuse."""
    structure = recording_structure(path)
    if not structure.data_parquet_path.exists():
        return dict(runs=[], selected_run_id=0)
    metadata = read_metadata(path=structure.data_parquet_path)
    runs = []
    for run_id, run in metadata.runs.items():
        groups = []
        for group in run.sensor_groups:
            kinds = {c.kind for c in run.channels if c.sensor_group == group}
            if not kinds.intersection((ChannelKind.OVERLAY_2D, ChannelKind.RAW_KEYPOINTS_3D, ChannelKind.KEYPOINTS_3D)):
                continue
            completed = {c.stage for c in run.checkpoints if c.sensor_group == group}
            stages = dict(
                observations=ChannelKind.OVERLAY_2D in kinds and ChannelKind.TIMESTAMPS in kinds,
                triangulation=ChannelKind.RAW_KEYPOINTS_3D in kinds,
                filtering=ChannelKind.KEYPOINTS_3D in kinds,
                scale_fit=any(f.sensor_group == group for f in run.scale_fits),
                reconstruction=ProcessingStage.RECONSTRUCTION in completed and {ChannelKind.LANDMARKS_3D, ChannelKind.MAPPED_KEYPOINTS_3D}.issubset(kinds),
                skeleton_fit=ProcessingStage.SKELETON_FIT in completed,
            )
            groups.append(dict(sensor_group=group, stages=stages))
        runs.append(dict(run_id=run_id, groups=groups))
    return dict(runs=runs, selected_run_id=metadata.selected_run_id)


def run_saved_numerical_stages(*, structure: RecordingStructure, config: PosthocMocapPipelineConfig,
                             reporter: TaskProgressReporter, cancelled: Callable[[], bool] | None = None) -> None:
    """Re-filter saved raw points or reconstruct using the exact saved scale fit.

    Saved triangulation fixes the coordinate frame. Alignment and camera settings
    belong to triangulation; this path never reapplies them to aligned points.
    """
    def check_cancelled():
        if cancelled is not None and cancelled():
            raise CancelledError('Processing cancelled; previous checkpoint retained')

    with recording_write_lock(structure=structure):
        check_cancelled()
        metadata = read_metadata(path=structure.data_parquet_path)
        if metadata.recording_id != structure.recording_name:
            raise ValueError('Recording identity does not match its directory')
        base = metadata.runs[config.base_run_id]
        group = select_group(base, config.sensor_group)
        start = ProcessingStage(config.start_stage)
        if start == ProcessingStage.SKELETON_FIT:
            # The solver manages its own lock below.
            pass
        else:
            provenance = ProvenanceContext.create()
            defaults = PosthocMocapPipelineConfig().model_dump(mode='json')
            kind = ChannelKind.RAW_KEYPOINTS_3D if start == ProcessingStage.FILTERING else ChannelKind.KEYPOINTS_3D
            channels = [c for c in base.channels if c.sensor_group == group and c.kind == kind]
            if len(channels) != 1:
                raise ValueError(f'Reprocessing requires one saved {kind} channel; rerun the preceding stage')
            points = read_saved_channel(structure=structure, run_id=config.base_run_id,
                metadata=metadata, channel=channels[0])
            if tuple(points.channel.components) != ('x', 'y', 'z'):
                raise ValueError('Saved spatial points must declare xyz components in order')
            reference = SpatialReference.model_validate(base.reference_frames[points.channel.reference_frame])
            report = None
            if start == ProcessingStage.FILTERING:
                reporter.report(stage='filtering', detail='Filtering saved 3D points; retaining their coordinate frame')
                prepared = prepare_recording_points(points=points.values,
                    timestamps_s=np.asarray(points.timestamps_s), config=config.filter_config)
                values, report = prepared.points, prepared.report
            else:
                values = points.values
                saved_report = base.processing.get(group, {}).get('filtering')
                if saved_report is not None:
                    report = PosthocFilterReport.model_validate(saved_report)
            support = report.gap_filling.measured_support(values) if report is not None and report.gap_filling is not None else None
            bundles = tuple(model.to_bundle() for model in base.models.values()
                if model_source_name(model.model_id) not in base.sources
                or base.sources[model_source_name(model.model_id)].definition.get('tracker') == points.channel.source)
            bundles = tuple(replace(bundle, anchor_segment_name=config.anchor_segment_name)
                if bundle.model_id == 'standard_human' else bundle for bundle in bundles)
            if not bundles:
                raise ValueError('Saved scientific models are missing; rerun triangulation')
            numerical = RecordingReconstructionInput(bundles=bundles, keypoint_names=points.channel.names,
                keypoints_3d=values, measured_support=support, compute_center_of_mass=True, timing=PosthocTimingReport())
            check_cancelled()
            reporter.report(stage='reconstructing', detail='Reconstructing from saved 3D points')
            if start == ProcessingStage.RECONSTRUCTION:
                fits = {bundle.model_id: next((f for f in base.scale_fits
                    if f.sensor_group == group and f.source == model_source_name(bundle.model_id)), None) for bundle in bundles}
                if any(f is None for f in fits.values()):
                    raise ValueError('Saved scale fit is missing; rerun filtering and scale fitting')
                results = reconstruct_skeletons_with_fits(request=numerical,
                    fits={name: FittedRecordingScale(inputs=f.inputs, fit=f.fit) for name, f in fits.items()})
            else:
                results = reconstruct_skeletons_for_recording(numerical)
            check_cancelled()
            reconstructions = tuple(ReconstructionRecording(sensor_group=group, reference=reference,
                definition=ReconstructionSourceDefinition.from_bundle(bundle, tracker_source=points.channel.source,
                    point_kind=ChannelKind.KEYPOINTS_3D), result=results[bundle.model_id]) for bundle in bundles)
            dependencies = stage_dependencies()
            invalidated = tuple(s for s in ProcessingStage if start in dependency_closure(stages={s}, dependencies=dependencies))
            executed = tuple(s for s in invalidated if s not in (ProcessingStage.SKELETON_FIT, ProcessingStage.REPROJECTION))
            plan = StageExecutionPlan(config.base_run_id, config.base_run_id, (group,), executed, invalidated)
            retained = retained_run(base=base, plan=plan)
            series = []
            if start == ProcessingStage.FILTERING:
                series.append(ChannelSeries(channel=points.channel.model_copy(update={
                    'kind': ChannelKind.KEYPOINTS_3D, 'stage': ProcessingStage.FILTERING}), values=values))
            for reconstruction in reconstructions:
                series.extend(reconstruction.series())
            data = retained.model_dump()
            from freemocap.core.recording.data_descriptors.recording_model import RecordedModel
            for bundle in bundles:
                data['models'][bundle.model_id] = RecordedModel.from_bundle(bundle)
            data['channels'] = (*retained.channels, *(item.channel for item in series))
            for reconstruction in reconstructions:
                data['sources'][reconstruction.definition.source_name] = reconstruction.definition.to_source()
                data['reference_frames'].update(reconstruction.reference_frames())
            if start == ProcessingStage.FILTERING:
                settings = dict(data['processing'].get(group, {}))
                settings['filtering'] = report.model_dump(mode='json')
                data['processing'][group] = settings
            if start in (ProcessingStage.FILTERING, ProcessingStage.SCALE_FIT):
                data['scale_fits'] = (*retained.scale_fits, *(item.to_scale_fit() for item in reconstructions))
            prepared_signature = SavedPointSeries(channel=points.channel.model_copy(update={
                'kind': ChannelKind.KEYPOINTS_3D, 'stage': ProcessingStage.FILTERING}),
                frames=points.frames, timestamps_s=points.timestamps_s, values=values).signature()
            point_signatures = {item.definition.model_id: prepared_signature for item in reconstructions}
            fit_signatures = {item.definition.model_id: definition_signature(item.to_scale_fit()) for item in reconstructions}
            model_signatures = {item.definition.model_id: definition_signature(dict(
                fit=fit_signatures[item.definition.model_id], points=prepared_signature,
                compute_center_of_mass=item.result.compute_center_of_mass,
                anchor_segment_name=config.anchor_segment_name)) for item in reconstructions}
            signatures = {
                ProcessingStage.FILTERING: definition_signature(dict(version=2,
                    raw_points={name: points.signature() for name in point_signatures},
                    points=point_signatures, filtering=report)),
                ProcessingStage.SCALE_FIT: definition_signature(dict(version=1, points=point_signatures, fits=fit_signatures)),
                ProcessingStage.RECONSTRUCTION: definition_signature(dict(version=1, models=model_signatures)),
                ProcessingStage.BIOMECHANICS: definition_signature(dict(version=1, models=model_signatures)),
            }
            data['checkpoints'] = (*retained.checkpoints, *(StageCheckpoint(sensor_group=group,
                stage=stage, signature=signatures[stage]) for stage in executed))
            entries = dict(stage_provenance(retained.processing, group).stages)
            for stage in executed:
                entries[stage] = provenance.record(
                    settings=stage_settings(stage, config.model_dump(mode='json'), filtering=report),
                    defaults=stage_settings(stage, defaults),
                    inputs=dict(points=points.signature(), models=base.models,
                        prepared_points=prepared_signature, fits=fit_signatures,
                        filtering_report=report),
                    sources=tuple(item.definition.source_name for item in reconstructions)
                        if stage != ProcessingStage.FILTERING else (points.channel.source,),
                    base_run_id=config.base_run_id, base_descriptor=base)
            data['processing'] = set_stage_provenance(data['processing'], group, entries)
            result = RunDescriptor.model_validate(data)
            sampling = SeriesSampling(points.frames, points.timestamps_s, config.base_run_id)
            check_cancelled()
            publish_checkpoint(structure=structure, metadata=metadata, plan=plan, result=result,
                computed_batches=(batch for item in series for batch in item.batches(sampling)))
    if config.skeleton_fit_enabled or config.start_stage == 'skeleton_fit':
        from freemocap.core.recording.result_processing.skeleton_fitting import fit_saved_skeleton
        check_cancelled()
        reporter.report(stage='fitting_skeleton', detail='Fitting the saved reconstructed skeleton')
        fit_saved_skeleton(structure=structure, run_id=config.base_run_id, sensor_group=group,
            cancelled=cancelled, force=config.start_stage == 'skeleton_fit')
