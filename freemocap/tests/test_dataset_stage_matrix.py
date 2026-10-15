"""Fast harness checks; the actual recording matrix is explicitly invoked."""
from freemocap.tools.datasets.stage_matrix import (
    stage_ranges, render_report, run_matrix, compare_reference_frame, validate_executed_operations,
)
from freemocap.tools.datasets.workflow import STARTS
import pytest


def test_every_contiguous_range_including_single_stages():
    ranges = stage_ranges()
    assert len(ranges) == len(set(ranges)) == 15
    assert all((stage, stage) in ranges for stage in STARTS)
    assert all(STARTS.index(start) <= STARTS.index(stop) for start, stop in ranges)


def test_failed_and_pending_ranges_cannot_count_as_passes():
    rows = [dict(start=a, stop=b, status='pending') for a, b in stage_ranges()]
    rows[0].update(status='passed', elapsed_s=1.0)
    rows[1].update(status='failed', error='Saved-stage restart rejected', elapsed_s=2.0)
    text = render_report(dict(ranges=rows))
    assert 'Passed: 1/15' in text
    assert 'Saved-stage restart rejected' in text
    assert 'ms/mocap frame' in text


def test_report_handles_saved_stage_task_without_live_frame_counter():
    row = dict(start='triangulation', stop='triangulation', status='passed', elapsed_s=2.0,
               application_timing=dict(elapsed_seconds=1.0, seconds_per_motion_frame=None, motion_frame_count=None))
    assert '4.50 ms/mocap frame (222 saved frames)' in render_report(dict(ranges=[row]))


def test_output_cannot_overlap_source(tmp_path):
    with pytest.raises(ValueError, match='separate'):
        run_matrix(recordings_root=tmp_path, output=tmp_path / 'output', calibration=tmp_path / 'unused')


def test_does_not_overwrite_existing_report(tmp_path):
    output = tmp_path / 'output'
    output.mkdir()
    with pytest.raises(ValueError, match='new output'):
        run_matrix(recordings_root=tmp_path / 'source', output=output, calibration=tmp_path / 'unused')


def test_tracking_only_may_not_yet_have_calibration_camera_assignment():
    expected = dict(camera_id='cam1', calibration_camera_id='cal1', width=720, height=1280)
    actual = dict(expected, calibration_camera_id=None)
    compare_reference_frame(expected, actual, tracking_only=True)
    with pytest.raises(ValueError, match='Coordinate frame'):
        compare_reference_frame(expected, actual, tracking_only=False)
    with pytest.raises(ValueError, match='Coordinate frame'):
        compare_reference_frame(expected, dict(actual, camera_id='cam2'), tracking_only=True)


def test_restart_must_not_replay_tracking_or_run_beyond_requested_finish():
    task = dict(status='complete', operations=[dict(operation_id=k, status='complete')
        for k in ('load_saved_observations', 'match_and_triangulate', 'align_reference')])
    validate_executed_operations(task, start='triangulation', stop='triangulation')
    task['operations'].append(dict(operation_id='load_and_track', status='complete'))
    with pytest.raises(ValueError, match='Wrong source'):
        validate_executed_operations(task, start='triangulation', stop='triangulation')
    task['operations'][-1]['operation_id'] = 'reconstruct_skeletons'
    with pytest.raises(ValueError, match='Unexpected execution'):
        validate_executed_operations(task, start='triangulation', stop='triangulation')


def test_saved_3d_restart_must_not_repeat_triangulation_or_alignment():
    task = dict(status='complete', operations=[dict(operation_id=k, status='complete')
        for k in ('filter_trajectories', 'fit_model_dimensions', 'reconstruct_skeletons')])
    validate_executed_operations(task, start='filtering', stop='reconstruction')
    task['operations'].append(dict(operation_id='align_reference', status='complete'))
    with pytest.raises(ValueError, match='Unexpected execution'):
        validate_executed_operations(task, start='filtering', stop='reconstruction')


def test_failed_full_baseline_never_turns_a_partial_run_into_its_own_reference(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from freemocap.tools.datasets import stage_matrix as matrix
    raw = tmp_path / 'raw'
    videos = raw / matrix.TEST_DATA.name / 'synchronized_videos'
    videos.mkdir(parents=True)
    video = videos / 'cam.mp4'
    video.write_bytes(b'copy-only fixture; worker is mocked')
    calibration = tmp_path / 'calibration.toml'
    calibration.write_text('fixture')
    source = dict(videos=[dict(filename=video.name, sha256=matrix.file_digest(video), nominal_fps=6.0)],
                  board_metadata={})
    monkeypatch.setattr(matrix, 'inspect_recording', lambda *args, **kwargs: source)
    monkeypatch.setattr(matrix, 'software_identity', lambda: {})
    calls = []

    def worker(command, **kwargs):
        path = Path(command[-1])
        request = json.loads(path.read_text())
        calls.append(request['stop_stage'])
        if request['stop_stage'] == 'reconstruction':
            raise RuntimeError('Full baseline failed')
        operations = ['load_and_track']
        if request['stop_stage'] != 'observations':
            operations += ['match_and_triangulate', 'align_reference']
        if request['stop_stage'] == 'scale_fit':
            operations += ['fit_model_dimensions']
        matrix.write_json(path.parent / 'result.json', dict(validation={}, mocap_config={},
            mocap_task=dict(status='complete', timing={}, operations=[dict(operation_id=k, status='complete') for k in operations])))

    monkeypatch.setattr(matrix, 'execute_worker', worker)
    comparisons = []
    monkeypatch.setattr(matrix, 'compare_stage_channels', lambda *args, **kwargs: comparisons.append(args))
    report = matrix.run_matrix(recordings_root=raw, calibration=calibration, output=tmp_path / 'out')
    assert len(report['ranges']) == 15
    assert all(row['status'] == 'failed' for row in report['ranges'])
    assert len(calls) == 5
    assert comparisons == []
