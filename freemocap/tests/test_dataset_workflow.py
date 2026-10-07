"""Dataset commands rerun explicitly and retain accepted results on failure."""

import json
from pathlib import Path
import subprocess
from unittest.mock import Mock

import pytest

from freemocap.tools.datasets import workflow, storage
from freemocap.tools.datasets.__main__ import main, parser


def generation(root, label):
    candidate = root / 'attempts' / label / 'current'
    recording = candidate / 'recordings' / 'recording'
    recording.mkdir(parents=True)
    (recording / 'data').write_text(label)
    return candidate, dict(recording=str(root / 'current/recordings/recording'), result=label)


def test_replacement_retains_previous_files_and_matching_marker(tmp_path):
    first, ready = generation(tmp_path, 'first')
    storage.save_current(tmp_path, first, ready)
    second, new = generation(tmp_path, 'second')
    storage.save_current(tmp_path, second, new)
    assert (Path(new['recording']) / 'data').read_text() == 'second'
    previous = next((tmp_path / 'history').glob('*/ready.json'))
    restored = json.loads(previous.read_text())
    assert (Path(restored['recording']) / 'data').read_text() == 'first'
    assert not (tmp_path / 'replacement.json').exists()


def test_failed_marker_save_restores_previous_result(tmp_path, monkeypatch):
    first, old = generation(tmp_path, 'first')
    storage.save_current(tmp_path, first, old)
    second, new = generation(tmp_path, 'second')
    write = storage.write_json

    def fail(path, value):
        if path.name == 'ready.json' and value == new:
            raise OSError('disk failure')
        write(path, value)

    monkeypatch.setattr(storage, 'write_json', fail)
    with pytest.raises(OSError, match='disk failure'):
        storage.save_current(tmp_path, second, new)
    assert json.loads((tmp_path / 'ready.json').read_text()) == old
    assert (Path(old['recording']) / 'data').read_text() == 'first'
    assert next((tmp_path / 'attempts').glob('interrupted-*/recordings/recording/data')).read_text() == 'second'


@pytest.mark.parametrize('moved_candidate', [False, True])
def test_restart_recovers_interrupted_directory_replacement(tmp_path, moved_candidate):
    first, old = generation(tmp_path, 'first')
    storage.save_current(tmp_path, first, old)
    second, new = generation(tmp_path, 'second')
    backup = tmp_path / 'history/previous'
    (tmp_path / 'current').rename(backup)
    storage.write_json(tmp_path / 'replacement.json', dict(old=old, new=new, backup=str(backup), candidate=str(second)))
    if moved_candidate:
        second.rename(tmp_path / 'current')
    assert storage.recover(tmp_path)
    assert (Path(old['recording']) / 'data').read_text() == 'first'
    assert json.loads((tmp_path / 'ready.json').read_text()) == old


def test_recovery_rejects_paths_outside_dataset(tmp_path):
    root = tmp_path / 'dataset'
    root.mkdir()
    storage.write_json(root / 'replacement.json', dict(old=None, new={}, backup=str(tmp_path / 'outside'), candidate=str(root / 'candidate')))
    with pytest.raises(ValueError, match='escapes'):
        storage.recover(root)


@pytest.fixture
def recording_workflow(tmp_path, monkeypatch):
    name = 'test_data'
    raw = tmp_path / 'raw' / workflow.TEST_DATA.name
    videos = raw / 'synchronized_videos'
    videos.mkdir(parents=True)
    video = videos / 'camera.mp4'
    video.write_bytes(b'original video')
    (raw / 'charuco_board_info.json').write_text('{}')
    source = dict(videos=[dict(filename=video.name, sha256=workflow.file_digest(video), nominal_fps=6)])
    monkeypatch.setattr(workflow, 'acquire_recording', lambda *a, **kw: raw)
    monkeypatch.setattr(workflow, 'inspect_recording', lambda *a, **kw: source)
    monkeypatch.setattr(workflow, 'software_identity', lambda: {'revision': 'current'})
    calls = []

    def worker(command, *, environment, log_path, timeout):
        request_path = Path(command[-1])
        request = json.loads(request_path.read_text())
        calls.append(request)
        recording = Path(request['recording'])
        calibration = recording / 'calibration.toml'
        calibration.write_text('calibration')
        parquet = recording / f'{recording.name}_data.parquet'
        if request['operation'] != 'calibrate':
            parquet.write_text(f'result {len(calls)}')
        result = dict(calibration_filename=calibration.name, calibration_sha256=workflow.file_digest(calibration),
            validation=dict(parquet_sha256=workflow.file_digest(parquet)) if parquet.exists() else None,
            mocap_config=dict(skeleton_fit_enabled=request['skeleton_fit']))
        storage.write_json(request_path.parent / 'result.json', result)
        log_path.write_text('completed')

    monkeypatch.setattr(workflow, 'execute_worker', worker)
    return name, dict(recordings_root=raw.parent, prepared_root=tmp_path / 'prepared'), calls


def test_processing_replaces_old_result_but_calibration_only_does_not(recording_workflow):
    name, options, calls = recording_workflow
    current = workflow.process(name, **options)
    parquet = current / f'{current.name}_data.parquet'
    assert parquet.read_text() == 'result 1'
    workflow.process(name, **options)
    assert parquet.read_text() == 'result 2'
    workflow.process(name, operation='calibrate', **options)
    assert parquet.read_text() == 'result 2'
    assert calls[0]['alignment'] == 'auto'
    assert calls[0]['skeleton_fit'] is False
    assert calls[0]['filtering_enabled'] is False
    assert (options['recordings_root'] / workflow.TEST_DATA.name / 'synchronized_videos/camera.mp4').read_bytes() == b'original video'


def test_worker_failure_leaves_current_recording_and_marker(recording_workflow, monkeypatch):
    name, options, _ = recording_workflow
    current = workflow.process(name, **options)
    marker = options['prepared_root'] / workflow.TEST_DATA.name / 'ready.json'
    before = marker.read_bytes()
    monkeypatch.setattr(workflow, 'execute_worker', Mock(side_effect=subprocess.CalledProcessError(1, 'worker')))
    with pytest.raises(RuntimeError, match='previous results retained'):
        workflow.process(name, **options)
    assert marker.read_bytes() == before
    assert (current / f'{current.name}_data.parquet').read_text() == 'result 1'


def test_skeleton_fit_can_be_explicitly_enabled(recording_workflow):
    name, options, calls = recording_workflow
    workflow.process(name, skeleton_fit=True, **options)
    assert calls[0]['skeleton_fit'] is True


@pytest.mark.parametrize('command', [['process', 'test_data'], ['process-all']])
@pytest.mark.parametrize('flags, enabled', [([], False), (['--skeleton-fit'], True), (['--no-skeleton-fit'], False)])
def test_cli_passes_explicit_fitting_policy_to_processing(monkeypatch, command, flags, enabled):
    process = Mock(return_value=Path('saved'))
    monkeypatch.setattr(workflow, 'process', process)
    assert main(command + flags) == 0
    assert process.called
    assert all(call.kwargs['skeleton_fit'] is enabled for call in process.call_args_list)


def test_conflicting_fitting_flags_are_rejected():
    with pytest.raises(SystemExit):
        parser().parse_args(['process', 'test_data', '--skeleton-fit', '--no-skeleton-fit'])


def test_realtime_fitting_defaults_off_but_can_be_enabled():
    from freemocap.core.pipeline.realtime.realtime_aggregator_node_config import RealtimeAggregatorNodeConfig
    assert RealtimeAggregatorNodeConfig().skeleton_fitting_enabled is False
    assert RealtimeAggregatorNodeConfig(skeleton_fitting_enabled=True).skeleton_fitting_enabled is True


def test_all_runs_test_data_first_and_stops_on_failure(monkeypatch):
    process = Mock(side_effect=RuntimeError('failed'))
    monkeypatch.setattr(workflow, 'process', process)
    assert main(['process-all']) == 1
    assert process.call_count == 1
    assert process.call_args.args == ('test_data',)
    process.reset_mock(side_effect=True)
    process.return_value = Path('saved')
    assert main(['process-all']) == 0
    assert [call.args[0] for call in process.call_args_list] == ['test_data', 'sample_data']


def test_dry_run_does_not_create_directories(tmp_path):
    assert main(['process', 'sample_data', '--dry-run', '--recordings-root', str(tmp_path / 'raw'),
                 '--prepared-root', str(tmp_path / 'prepared')]) == 0
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('options', [dict(start='skeleton_fit', skeleton_fit=False),
    dict(start='filtering', calibration='fresh'), dict(start='reconstruction', alignment='person')])
def test_invalid_restart_options_fail_before_writes(tmp_path, options):
    with pytest.raises(ValueError):
        workflow.preflight('test_data', recordings_root=tmp_path / 'raw', prepared_root=tmp_path / 'prepared', **options)
    assert not list(tmp_path.iterdir())


def test_outputs_cannot_overlap_raw_recordings(tmp_path):
    with pytest.raises(ValueError, match='separate'):
        workflow.process('test_data', recordings_root=tmp_path, prepared_root=tmp_path / 'prepared')
    assert not list(tmp_path.iterdir())


def test_dataset_names_are_explicit():
    with pytest.raises(SystemExit):
        parser().parse_args(['process', 'test'])


def test_concurrent_processing_does_not_touch_active_attempt(recording_workflow):
    from filelock import FileLock, Timeout
    name, options, _ = recording_workflow
    workflow.process(name, **options)
    root = options['prepared_root'] / workflow.TEST_DATA.name
    attempts = set((root / 'attempts').iterdir())
    with FileLock(str(root / 'prepare.lock'), timeout=0):
        with pytest.raises(Timeout):
            workflow.process(name, **options)
    assert set((root / 'attempts').iterdir()) == attempts


def test_completed_save_with_leftover_journal_keeps_new_result(tmp_path):
    first, old = generation(tmp_path, 'first')
    storage.save_current(tmp_path, first, old)
    second, new = generation(tmp_path, 'second')
    backup = tmp_path / 'history/previous'
    (tmp_path / 'current').rename(backup)
    second.rename(tmp_path / 'current')
    storage.write_json(tmp_path / 'ready.json', new)
    storage.write_json(tmp_path / 'replacement.json', dict(old=old, new=new, backup=str(backup), candidate=str(second)))
    assert storage.recover(tmp_path)
    assert (Path(new['recording']) / 'data').read_text() == 'second'


def test_long_windows_video_path_is_rejected_before_worker(recording_workflow, monkeypatch):
    name, options, calls = recording_workflow
    monkeypatch.setattr(workflow.os, 'name', 'nt')
    options['prepared_root'] = options['prepared_root'] / ('long-root-' * 12)
    with pytest.raises(ValueError, match='shorter --prepared-root'):
        workflow.process(name, **options)
    assert not calls
