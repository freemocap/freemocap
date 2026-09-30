"""Run the packaged Forge human fit on saved reconstruction channels.

No tracking, interpolation, alignment or geometry correction is performed here.
The caller explicitly chooses the recording run and sensor group. Publication
uses the existing atomic checkpoint writer; failure leaves the prior file intact.
"""
from collections.abc import Callable
from concurrent.futures import CancelledError
from dataclasses import dataclass
import hashlib
import importlib.metadata
import json
import logging
from time import perf_counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pyarrow.compute as pc
from skellyforge import _native
from skellyforge.core.skeleton import fitting
from skellyforge.core.skeleton.fitting import fit_human

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.pipeline.posthoc.stage_execution_plan import StageExecutionPlan, retained_run
from freemocap.core.recording.data_descriptors.recording_descriptor import (
    Channel, RecordingMetadata, Source, SourceKind, StageCheckpoint,
)
from freemocap.core.recording.data_descriptors.recording_model import RecordedModel
from freemocap.core.recording.data_descriptors.scale_fit import RecordingScaleFit
from freemocap.core.recording.parquet_storage.parquet_reader import read_batches, read_metadata
from freemocap.core.recording.parquet_storage.parquet_writer import recording_write_lock
from freemocap.core.recording.parquet_storage.checkpoint_publication import publish_checkpoint
from freemocap.core.recording.result_processing.input_signatures import definition_signature, point_array_signature
from freemocap.core.recording.sample_encoding.arrow_schema import SampleValidator
from freemocap.core.recording.sample_encoding.channel_series import ChannelSeries, SeriesSampling
from freemocap.core.recording.sample_encoding.reconstruction_samples import model_source_name
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.system.recording_structure.recording_structure import RecordingStructure

logger = logging.getLogger(__name__)
STAGE = ProcessingStage.SKELETON_FIT


def _json_value(value):
    """Serialize actual Forge outputs; no second model or solver schema."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f'Unsupported fitted metadata: {type(value).__name__}')


def solver_provenance() -> dict:
    paths = [Path(_native.__file__), *sorted(Path(fitting.__file__).parent.glob('*.py'))]
    return dict(
        adapter_version=2,
        package_version=importlib.metadata.version('skellyforge'),
        ceres_version=_native.ceres_version,
        code_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
    )


@dataclass(frozen=True)
class SavedSkeletonFitInputs:
    records: list[dict]
    model: RecordedModel
    scale_fit: RecordingScaleFit
    reference_frame: str
    signature: str


def read_fit_inputs(*, path: Path, metadata: RecordingMetadata, run_id: int,
                    sensor_group: str, model_id: str) -> SavedSkeletonFitInputs:
    """Load exactly the prepared channels used by the standalone Forge fit."""
    run = metadata.runs[run_id]
    model = run.models[model_id]
    if model_id != 'standard_human':
        raise ValueError('The accepted human solver currently supports standard_human only')
    source = model_source_name(model_id)
    definition = run.sources[source].definition
    if definition['point_kind'] != ChannelKind.KEYPOINTS_3D:
        raise ValueError('Skeleton fitting requires prepared keypoint trajectories')
    selected = {}
    for field, kind, producer, components in (
        ('points', ChannelKind.LANDMARKS_3D, source, dict.fromkeys('xyz', 'mm')),
        ('keypoints', ChannelKind.KEYPOINTS_3D, definition['tracker'], dict.fromkeys('xyz', 'mm')),
        ('origins', ChannelKind.SEGMENT_ORIGINS, source, dict.fromkeys('xyz', 'mm')),
        ('rotations', ChannelKind.ROTATIONS_WORLD, source, dict.fromkeys('wxyz', '1')),
    ):
        matches = [c for c in run.channels if c.sensor_group == sensor_group
                   and c.source == producer and c.kind == kind]
        if len(matches) != 1 or matches[0].components != components:
            raise ValueError(f'Expected one prepared {field} channel in {components}')
        selected[field] = matches[0]
    reference = selected['points'].reference_frame
    if any(c.reference_frame != reference for c in selected.values()):
        raise ValueError('Fitting inputs must share their spatial reference')
    if run.reference_frames[reference].get('basis') != 'blender_x_right_y_forward_z_up':
        raise ValueError('Unsupported skeleton-fit coordinate basis')
    fits = [f for f in run.scale_fits if f.source == source
            and f.sensor_group == sensor_group and f.reference_frame == reference]
    if len(fits) != 1 or fits[0].fit is None or fits[0].units != 'mm':
        raise ValueError('Skeleton fitting requires a completed person-scale fit in millimeters')
    subset = metadata.model_copy(update={'runs': {run_id: run.model_copy(update={'channels': tuple(selected.values())})}})
    validator = SampleValidator(subset)
    frames = {}
    for batch in read_batches(path=path, run_id=run_id, sensor_groups=(sensor_group,)):
        for field, channel in selected.items():
            mask = pc.and_(pc.equal(batch.column('source'), channel.source),
                           pc.equal(batch.column('channel'), channel.kind))
            mask = pc.and_(mask, pc.equal(batch.column('reference_frame'), reference))
            part = batch.filter(mask)
            if not part.num_rows:
                continue
            validator.accept(batch=part)
            for row in part.to_pylist():
                record = frames.setdefault(row['frame_number'], dict(number=row['frame_number'], time=row['timestamp_s'],
                    points={}, keypoints={}, origins={}, rotations={}))
                if record['time'] != row['timestamp_s']:
                    raise ValueError('Fitting input channels disagree on timestamps')
                components = tuple(channel.components)
                vector = record[field].get(row['name'])
                if vector is None:
                    vector = np.full(len(components), np.nan)
                    record[field][row['name']] = vector
                vector[components.index(row['component'])] = np.nan if row['value'] is None else row['value']
    validator.finish()
    records = [frames[k] for k in sorted(frames)]
    if len(records) < 3:
        raise ValueError('Skeleton fitting requires at least three frames')
    fingerprints = {}
    for field, channel in selected.items():
        values = np.asarray([[r[field][n] for n in channel.names] for r in records])
        fingerprints[field] = dict(channel=channel, values=point_array_signature(values))
        # Entirely absent keypoint tracks are not fabricated observations. Forge
        # retains the complete model and supplies its existing rest-pose behavior.
        for record in records:
            record[field] = {n: v for n, v in record[field].items() if np.isfinite(v).all()}
    signature = definition_signature(dict(model=model, scale_fit=fits[0], channels=fingerprints,
        frames=[(r['number'], r['time']) for r in records], solver=solver_provenance()))
    return SavedSkeletonFitInputs(records, model, fits[0], reference, signature)


@dataclass
class RecordingHumanFit:
    model: dict
    sequence: object
    landmarks: dict

    def landmark_positions(self):
        return self.landmarks


def fit_visible_intervals(inputs: SavedSkeletonFitInputs, *, progress=None):
    """Fit prepared visible intervals independently; retain nulls on the saved grid.

    Input channels already went through Forge gap filling. Never fill again here
    or carry a root seed or temporal residual across a completely absent frame.
    """
    records = inputs.records
    visible = np.array([bool(r['keypoints']) for r in records])
    boundaries = np.flatnonzero(np.diff(np.r_[False, visible, False])).reshape(-1, 2)
    skeleton = inputs.model.skeleton.restore()
    saved_model = inputs.model.model_dump(mode='json')
    # The authored tree determines the root; dictionary insertion order does not.
    from skellyforge.core.skeleton.pose.rest_pose import RestPose
    root = RestPose.default_for(skeleton=skeleton).root_segment_name
    usable, skipped = [], []
    for start, stop in boundaries.tolist():
        interval = records[start:stop]
        reason = ('fewer_than_three_frames' if stop - start < 3 else
                  'no_root_pose_in_interval' if not any(root in r['rotations'] and root in r['origins'] for r in interval) else None)
        if reason:
            skipped.append(dict(start=start, stop=stop, reason=reason))
        else:
            usable.append((start, stop))
    total = sum(stop - start - 2 for start, stop in usable)
    fits, windows, offset = [], [], 0
    for start, stop in usable:
        def on_progress(window, _total):
            if progress:
                adjusted = dict(window, index=offset + window['index'])
                for key in ('fixed_start', 'active_start', 'active_end'):
                    if key in adjusted: adjusted[key] += start
                progress(adjusted, total)
        fit = fit_human(skeleton, saved_model, inputs.scale_fit.fit.segment_scales,
                        records[start:stop], progress=on_progress)
        for window in fit.sequence.processing['windows']:
            adjusted = dict(window, index=offset + window['index'])
            for key in ('fixed_start', 'active_start', 'active_end'):
                if key in adjusted: adjusted[key] += start
            windows.append(adjusted)
        fits.append((start, stop, fit))
        offset += stop - start - 2
    if len(fits) == 1 and usable == [(0, len(records))]:
        return fits[0][2]
    if fits:
        model = fits[0][2].model
    else:
        from skellyforge.core.skeleton.fitting.body_model import body_model
        from skellyforge.core.skeleton.fitting.human import human_fit_options
        model = body_model(skeleton, saved_model, inputs.scale_fit.fit.segment_scales,
                           human_fit_options()['shoulder_profile'], flexible_cervical=True)
    n, b = len(records), len(model['names'])
    arrays = {name: np.full((n, b, width), np.nan) for name, width in
              [('quaternions', 4), ('translations', 3), ('linkage_displacements', 3)]}
    arrays['lengths'] = np.full((n, b), np.nan)
    landmarks = {name: np.full((n, 3), np.nan) for names in model['display_names'] for name in names}
    intervals = []
    for start, stop, fit in fits:
        for name in arrays: arrays[name][start:stop] = getattr(fit.sequence, name)
        for name, values in fit.landmark_positions().items(): landmarks[name][start:stop] = values
        intervals.append(dict(start=start, stop=stop, processing=fit.sequence.processing))
    present = np.zeros(n, dtype=bool)
    for start, stop in usable: present[start:stop] = True
    sequence = SimpleNamespace(**arrays, processing=dict(windows=windows, intervals=intervals,
        skipped_intervals=skipped, fitted_frames=present.tolist()),
        converged=bool(fits) and not skipped and all(f.sequence.converged for _, _, f in fits),
        report=f'{len(fits)} independent visible intervals; {len(skipped)} unsupported intervals left null')
    return RecordingHumanFit(model, sequence, landmarks)


def fitted_channels(*, fit, sensor_group: str, source: str, reference_frame: str) -> tuple[ChannelSeries, ...]:
    """Persist native state, including flexible geometry and relaxed linkages."""
    model, result = fit.model, fit.sequence
    series = []
    for kind, components, values in (
        (ChannelKind.SEGMENT_ORIGINS, dict.fromkeys('xyz', 'mm'), result.translations),
        (ChannelKind.ROTATIONS_WORLD, dict.fromkeys('wxyz', '1'), result.quaternions),
        (ChannelKind.LINKAGE_DISPLACEMENTS, dict.fromkeys('xyz', 'mm'), result.linkage_displacements),
    ):
        series.append(ChannelSeries(Channel(sensor_group=sensor_group, source=source,
            reference_frame=None if kind == ChannelKind.LINKAGE_DISPLACEMENTS else reference_frame,
            kind=kind, names=tuple(model['names']), components=components, stage=STAGE),
            np.asarray(values, dtype=np.float64)))
    flexible = np.asarray(model['references']) > 0
    series.append(ChannelSeries(Channel(sensor_group=sensor_group, source=source,
        reference_frame=reference_frame, kind=ChannelKind.SEGMENT_LENGTHS,
        names=tuple(n for n, keep in zip(model['names'], flexible) if keep), components={'length': 'mm'}, stage=STAGE),
        np.asarray(result.lengths, dtype=np.float64)[:, flexible, None]))
    landmarks = fit.landmark_positions()
    series.append(ChannelSeries(Channel(sensor_group=sensor_group, source=source,
        reference_frame=reference_frame, kind=ChannelKind.LANDMARKS_3D,
        names=tuple(landmarks), components=dict.fromkeys('xyz', 'mm'), stage=STAGE),
        np.stack(list(landmarks.values()), axis=1)))
    present = np.asarray(result.processing.get('fitted_frames', [True] * len(result.quaternions)))
    if any(not np.isfinite(item.values[present]).all() or not np.isnan(item.values[~present]).all() for item in series):
        raise ValueError('Fitted channels must be complete on fitted frames and null on absent frames')
    return tuple(series)


def fit_saved_skeleton(*, structure: RecordingStructure, run_id: int, sensor_group: str,
                       model_id: str = 'standard_human', keep: bool = False,
                       progress: Callable | None = None, cancelled: Callable[[], bool] | None = None,
                       force: bool = False) -> RecordingMetadata:
    """Explicit optional stage; never invoked by reading or rendering a recording.

    Cancellation is checked before solving, between windows and before publishing.
    An active native window finishes before the cancellation can be observed.
    """
    def check_cancelled():
        if cancelled is not None and cancelled():
            raise CancelledError('Skeleton fitting cancelled; no checkpoint published')

    def on_progress(window, total):
        check_cancelled()
        if progress is not None:
            progress(window, total)

    with recording_write_lock(structure=structure):
        check_cancelled()
        metadata = read_metadata(path=structure.data_parquet_path)
        logger.info('Loading prepared skeleton-fit inputs: run=%d, sensor_group=%s', run_id, sensor_group)
        started = perf_counter()
        inputs = read_fit_inputs(path=structure.data_parquet_path, metadata=metadata,
            run_id=run_id, sensor_group=sensor_group, model_id=model_id)
        loaded = perf_counter()
        logger.info('Skeleton-fit inputs loaded: frames=%d, seconds=%.3f', len(inputs.records), loaded - started)
        base = metadata.runs[run_id]
        source = f'skeleton_fit:{sensor_group}:{model_id}'
        completed = next((c for c in base.checkpoints if c.sensor_group == sensor_group and c.stage == STAGE), None)
        saved_source = base.sources.get(source)
        saved_kinds = {c.kind for c in base.channels if c.source == source and c.sensor_group == sensor_group and c.stage == STAGE}
        complete_channels = saved_kinds == {ChannelKind.SEGMENT_ORIGINS, ChannelKind.ROTATIONS_WORLD,
            ChannelKind.LINKAGE_DISPLACEMENTS, ChannelKind.SEGMENT_LENGTHS, ChannelKind.LANDMARKS_3D}
        if (completed is not None and completed.signature == inputs.signature and not keep and not force
                and saved_source is not None and saved_source.definition.get('input_signature') == inputs.signature
                and complete_channels):
            logger.info('Reusing skeleton fit: run=%d, sensor_group=%s', run_id, sensor_group)
            return metadata
        logger.info('Fitting saved skeleton: run=%d, sensor_group=%s, frames=%d', run_id, sensor_group, len(inputs.records))
        fitted = fit_visible_intervals(inputs, progress=on_progress)
        solved = perf_counter()
        logger.info('Skeleton solve complete: frames=%d, seconds=%.3f', len(inputs.records), solved - loaded)
        check_cancelled()
        series = fitted_channels(fit=fitted, sensor_group=sensor_group, source=source, reference_frame=inputs.reference_frame)
        plan = StageExecutionPlan(run_id, max(metadata.runs) + 1 if keep else run_id,
            (sensor_group,), (STAGE,), (STAGE,))
        retained = retained_run(base=base, plan=plan)
        # The fitted source contains the actual returned geometry, not a model
        # reconstructed by the viewer from today's defaults.
        definition = json.loads(json.dumps(dict(model_id=model_id, sensor_group=sensor_group,
            input_source=model_source_name(model_id), linkage_displacement_frame='parent_segment_local',
            geometry=fitted.model, solver=solver_provenance(), input_signature=inputs.signature,
            processing=fitted.sequence.processing, converged=fitted.sequence.converged,
            report=fitted.sequence.report), default=_json_value, allow_nan=False))
        result_data = retained.model_dump()
        result_data['sources'][source] = Source(kind=SourceKind.SOLVER, definition=definition).model_dump()
        result_data['channels'] = (*retained.channels, *(s.channel for s in series))
        result_data['checkpoints'] = (*retained.checkpoints, StageCheckpoint(sensor_group=sensor_group, stage=STAGE, signature=inputs.signature))
        result = type(retained).model_validate(result_data)
        sampling = SeriesSampling(tuple(r['number'] for r in inputs.records), tuple(r['time'] for r in inputs.records), plan.target_run_id)
        check_cancelled()
        logger.info('Publishing skeleton-fit checkpoint: run=%d, frames=%d, converged=%s',
            plan.target_run_id, len(inputs.records), fitted.sequence.converged)
        publishing = perf_counter()
        published = publish_checkpoint(structure=structure, metadata=metadata, plan=plan, result=result,
            computed_batches=(batch for item in series for batch in item.batches(sampling)))
        logger.info('Skeleton-fit checkpoint published: %s; publication_seconds=%.3f, total_seconds=%.3f',
            structure.data_parquet_path, perf_counter() - publishing, perf_counter() - started)
        return published
