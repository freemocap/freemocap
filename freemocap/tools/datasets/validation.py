"""Acceptance checks for saved reference recordings, without running processing."""

from pathlib import Path
import numpy as np

from freemocap.tools.datasets.preparation import validate_parquet


def validate_outputs(recording: Path, *, expected_frames: int, require_fit: bool,
                     run_id: int | None = None, sensor_group: str | None = None,
                     require_alignment: bool = False,
                     require_provenance_stages: tuple[str, ...] = ()) -> dict:
    from freemocap.core.pipeline.posthoc.saved_stage_processing import recording_structure, select_group
    from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
    from freemocap.core.recording.result_processing.saved_reconstruction import read_saved_channel

    report = validate_parquet(recording, expected_frames=expected_frames)
    structure = recording_structure(str(recording))
    metadata = read_metadata(path=structure.data_parquet_path)
    run_id = metadata.selected_run_id if run_id is None else run_id
    run = metadata.runs[run_id]
    group = select_group(run, sensor_group)
    outcomes = {name: reference.get('alignment', {}).get('outcome')
                for name, reference in run.reference_frames.items() if reference.get('alignment')}
    if require_alignment and (not outcomes or any(value not in (
            'foot_support', 'body_reference', 'preserved_reference') for value in outcomes.values())):
        raise ValueError(f'Reference alignment did not succeed: {outcomes}')
    fit_source = f'skeleton_fit:{group}:standard_human'
    kinds = {'SEGMENT_ORIGINS', 'ROTATIONS_WORLD', 'LINKAGE_DISPLACEMENTS', 'SEGMENT_LENGTHS', 'LANDMARKS_3D'}
    fit_channels = [c for c in run.channels if c.source == fit_source and c.sensor_group == group]
    if require_fit:
        if {c.kind for c in fit_channels} != kinds or not any(
                c.stage == 'skeleton_fit' and c.sensor_group == group for c in run.checkpoints):
            raise ValueError('Missing complete skeleton-fit channels/checkpoint')
        if fit_source not in run.sources:
            raise ValueError('Missing skeleton-fit metadata')
    # Check the actual fitted arrays, including their frame grid and rotation norms.
    reference_frames = None
    reference_times = None
    present = np.ones(expected_frames, dtype=bool)
    if require_fit:
        present = np.asarray(run.sources[fit_source].definition['processing'].get('fitted_frames', present))
        if present.shape != (expected_frames,) or present.dtype != np.bool_:
            raise ValueError('Fitted-frame mask must match the recording grid')
    for channel in fit_channels if require_fit else ():
        series = read_saved_channel(structure=structure, run_id=run_id, metadata=metadata, channel=channel)
        if len(series.frames) != expected_frames or len(set(series.frames)) != expected_frames:
            raise ValueError(f'Incomplete fitted frame grid: {channel.kind}')
        times = np.asarray(series.timestamps_s)
        if not np.isfinite(times).all() or not np.all(np.diff(times) > 0):
            raise ValueError('Fitted timestamps must be finite and increasing')
        if reference_frames is not None and (series.frames != reference_frames or not np.array_equal(times, reference_times)):
            raise ValueError('Fitted channels have different frame grids')
        reference_frames, reference_times = series.frames, times
        if not np.isfinite(series.values[present]).all() or not np.isnan(series.values[~present]).all():
            raise ValueError(f'Fitted values disagree with frame presence: {channel.kind}')
        if channel.kind == 'ROTATIONS_WORLD' and not np.allclose(
                np.linalg.norm(series.values[present], axis=-1), 1.0, atol=1e-6, rtol=0):
            raise ValueError('Fitted rotations are not unit quaternions')
    report.update(run_id=run_id, sensor_group=group, alignment_outcomes=outcomes,
                  skeleton_fit_checked=require_fit, fitted_frame_count=int(present.sum()) if require_fit else None)
    from freemocap.core.recording.data_descriptors.stage_provenance import stage_provenance
    provenance = stage_provenance(run.processing, group).stages
    missing = set(require_provenance_stages) - set(provenance)
    if missing:
        raise ValueError(f'Missing executed-stage provenance: {sorted(missing)}')
    if 'filtering' in provenance:
        actual = run.processing[group]['filtering']['config']
        if provenance['filtering'].effective_settings != actual:
            raise ValueError('Filter provenance disagrees with the published filtering report')
    report['provenance_stages'] = {stage: dict(attempt_id=entry.attempt_id,
        recorded_at=entry.recorded_at.isoformat(), defaults_saved=entry.default_settings is not None)
        for stage, entry in provenance.items()}
    return report
