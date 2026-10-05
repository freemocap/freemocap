"""Real Forge solve -> canonical Parquet -> reload, without touching prepared data."""
import hashlib
import os
from concurrent.futures import CancelledError
from pathlib import Path
import shutil

import numpy as np
import pyarrow.parquet as pq
import pytest

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.pipeline.posthoc.stage_execution_plan import StageExecutionPlan, retained_run
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.recording.playback_queries import playback_manifest
from freemocap.core.recording.result_processing import skeleton_fitting as stage
from freemocap.system.recording_structure.recording_structure import RecordingStructure


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


@pytest.fixture(params=['freemocap_test_data', 'freemocap_sample_data'])
def recording(tmp_path, request):
    name = request.param
    root = Path(os.environ.get('FREEMOCAP_PROVENANCE_PREPARED_ROOT', Path.home() / 'freemocap_data/testing/prepared'))
    path = root / name / 'current/recordings' / name / f'{name}_data.parquet'
    if not path.is_file():
        pytest.skip(f'Prepare {name} through the production pipeline first')
    structure = RecordingStructure(base_directory=tmp_path, recording_name=name)
    structure.full_path.mkdir(parents=True)
    shutil.copy2(path, structure.data_parquet_path)
    return structure


@pytest.mark.slow
def test_real_solver_checkpoint_round_trip_and_reuse(recording, monkeypatch):
    before = read_metadata(path=recording.data_parquet_path)
    run_id = before.selected_run_id
    group = next(iter(before.runs[run_id].sensor_groups))
    captured = []
    solver = stage.fit_visible_intervals

    def capture(*args, **kwargs):
        result = solver(*args, **kwargs)
        captured.append(result)
        return result

    monkeypatch.setattr(stage, 'fit_visible_intervals', capture)
    progress = []
    published = stage.fit_saved_skeleton(structure=recording, run_id=run_id,
        sensor_group=group, force=True, progress=lambda window, total: progress.append((window['index'], total)))
    assert len(captured) == 1
    frame_count = before.runs[run_id].sensor_groups[group].sample_count
    fitted = captured[0]
    windows = fitted.sequence.processing['windows']
    assert progress[-1] == (len(windows) - 1, len(windows))
    assert len(fitted.sequence.quaternions) == frame_count
    run = published.runs[run_id]
    source = next(name for name, value in run.sources.items() if value.kind == 'solver')
    saved = run.sources[source].definition
    assert saved['geometry']['names'] == fitted.model['names']
    assert saved['linkage_displacement_frame'] == 'parent_segment_local'
    assert saved['processing']['windows'] == fitted.sequence.processing['windows']
    assert run.models == before.runs[run_id].models
    assert run.scale_fits == before.runs[run_id].scale_fits
    for channel in before.runs[run_id].channels:
        assert channel in run.channels
    manifest = playback_manifest(recording.data_parquet_path)
    assert manifest.recording_id == recording.recording_name
    playback_run = next(item for item in manifest.runs if item.run_id == run_id)
    assert playback_run.fitted_skeletons[source] == saved
    assert source not in playback_run.model_sources, 'A solver is not another original reconstruction'
    expected = stage.fitted_channels(fit=fitted, sensor_group=group, source=source,
        reference_frame=next(c.reference_frame for c in run.channels if c.source == source and c.kind == 'ROTATIONS_WORLD'))
    for item in expected:
        table = pq.read_table(recording.data_parquet_path, filters=[('run_id', '=', run_id),
            ('source', '=', source), ('channel', '=', item.channel.kind)])
        values = np.asarray(table.column('value')).reshape(item.values.shape)
        np.testing.assert_array_equal(values, item.values)
    completed_hash = digest(recording.data_parquet_path)
    stage.fit_saved_skeleton(structure=recording, run_id=run_id, sensor_group=group)
    assert len(captured) == 1, 'Identical inputs must reuse the completed fit'
    assert digest(recording.data_parquet_path) == completed_hash
    plan = StageExecutionPlan(run_id, run_id, (group,), (ProcessingStage.RECONSTRUCTION,),
        (ProcessingStage.RECONSTRUCTION, ProcessingStage.SKELETON_FIT))
    retained = retained_run(base=run, plan=plan)
    assert not any(c.stage == ProcessingStage.SKELETON_FIT for c in retained.channels)
    assert not any(c.stage == ProcessingStage.SKELETON_FIT for c in retained.checkpoints)
    assert source not in retained.sources


def test_failure_and_cancellation_preserve_recording(recording, monkeypatch):
    before = digest(recording.data_parquet_path)
    metadata = read_metadata(path=recording.data_parquet_path)
    kwargs = dict(structure=recording, run_id=metadata.selected_run_id,
        sensor_group=next(iter(metadata.runs[metadata.selected_run_id].sensor_groups)))
    with pytest.raises(CancelledError):
        stage.fit_saved_skeleton(**kwargs, cancelled=lambda: True)
    assert digest(recording.data_parquet_path) == before

    def fail(*args, **kwargs):
        raise RuntimeError('Injected solver failure')

    monkeypatch.setattr(stage, 'fit_human', fail)
    with pytest.raises(RuntimeError, match='Injected solver failure'):
        stage.fit_saved_skeleton(**kwargs, force=True)
    assert digest(recording.data_parquet_path) == before
