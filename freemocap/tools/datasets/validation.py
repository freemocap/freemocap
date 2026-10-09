"""Acceptance checks for saved reference recordings, without running processing."""

from pathlib import Path

from freemocap.tools.datasets.preparation import validate_parquet


def validate_outputs(recording: Path, *, expected_frames: int,
                     run_id: int | None = None, sensor_group: str | None = None,
                     require_alignment: bool = False,
                     require_provenance_stages: tuple[str, ...] = ()) -> dict:
    from freemocap.core.pipeline.posthoc.saved_stage_processing import recording_structure, select_group
    from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata

    report = validate_parquet(recording, expected_frames=expected_frames)
    structure = recording_structure(str(recording))
    from freemocap.core.recording.parquet_storage.recording_view import recording_view
    with recording_view(structure.data_parquet_path) as view:
        report['source_revision'] = view.revision
    metadata = read_metadata(path=structure.data_parquet_path)
    run_id = metadata.selected_run_id if run_id is None else run_id
    run = metadata.runs[run_id]
    group = select_group(run, sensor_group)
    outcomes = {name: reference.get('alignment', {}).get('outcome')
                for name, reference in run.reference_frames.items() if reference.get('alignment')}
    if require_alignment and (not outcomes or any(value not in (
            'foot_support', 'body_reference', 'preserved_reference') for value in outcomes.values())):
        raise ValueError(f'Reference alignment did not succeed: {outcomes}')
    report.update(run_id=run_id, sensor_group=group, alignment_outcomes=outcomes)
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
