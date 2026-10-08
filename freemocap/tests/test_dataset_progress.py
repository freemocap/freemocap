"""Display checks use real Rich rendering without running camera pipelines."""

from io import StringIO

import pytest
from rich.console import Console

from freemocap.tools.datasets.progress import WorkerProgress


@pytest.fixture(autouse=True)
def terminal_environment(monkeypatch):
    monkeypatch.setenv('TERM', 'xterm-256color')


def test_live_rates_use_count_deltas_and_reset_for_each_stage():
    console = Console(file=StringIO(), force_terminal=True, width=170)
    with WorkerProgress('processing.log', console=console) as display:
        display.feed('2026-09-29 13:00:00,000 INFO calibration: Board detection in videos: 65/666 camera frames processed (running)')
        assert display.progress.tasks[0].fields['rate'] == ''
        display.feed('2026-09-29 13:00:02,000 INFO calibration: Board detection in videos: 165/666 camera frames processed (running)')
        assert display.progress.tasks[0].fields['rate'] == '  | AVG  50.00 FR/s  |  0.0200 s/FR |  '
        display.feed('2026-09-29 13:00:03,000 INFO calibration: Running anipose solver (running)')
        assert display.progress.tasks[0].fields['rate'] == ''
        display.feed('2026-09-29 13:00:04,000 INFO mocap: Detecting and annotating 4/222 synchronized frames (running)')
        display.feed('2026-09-29 13:00:06,000 INFO mocap: Detecting and annotating 24/222 synchronized frames (running)')
        assert display.progress.tasks[1].fields['rate'] == '  | AVG  10.00 FR/s  |  0.1000 s/FR |  '


def test_live_rates_handle_stalls_zero_time_and_counter_restarts():
    display = WorkerProgress('processing.log')
    assert display.rate_text('mocap', 'tracking', 'frames', 10, 100, 1) == ''
    assert display.rate_text('mocap', 'tracking', 'frames', 20, 100, 1) == ''
    assert display.rate_text('mocap', 'tracking', 'frames', 10, 100, 2) == ''
    assert display.rate_text('mocap', 'tracking', 'frames', 10, 100, 3) == '  | AVG  0.00 FR/s  |  -- s/FR |  '


def test_stage_change_clears_old_frame_total_and_preserves_completed_calibration():
    stream = StringIO()
    console = Console(file=stream, force_terminal=True, width=120)
    with WorkerProgress('processing.log', console=console) as display:
        display.feed('INFO calibration: Board detection in videos: 52/666 camera frames processed (running)\n')
        display.progress.tasks[0].start_time -= 5
        started = display.progress.tasks[0].start_time
        display.feed('INFO calibration: Running anipose solver (running)\n')
        assert display.progress.tasks[0].total is None
        display.feed('INFO calibration:  (complete)\n')
        display.feed('INFO mocap: Detecting and annotating 4/222 synchronized frames (running)\n')
        assert display.progress.tasks[0].finished
        assert display.progress.tasks[0].start_time == started
        assert display.progress.tasks[0].elapsed >= 5
        assert display.progress.tasks[1].total == 222
        display.feed('INFO mocap: Reconstructing skeleton (running)\n')
        assert display.progress.tasks[1].total is None
    assert 'FreeMoCap' in stream.getvalue()
    assert 'Reconstructing skeleton' in stream.getvalue()


def test_failure_is_visible_and_terminal_is_restored():
    stream = StringIO()
    console = Console(file=stream, force_terminal=True, width=120)
    with pytest.raises(RuntimeError), WorkerProgress('processing.log', console=console) as display:
        display.feed("INFO mocap: KeyError: 'pelvis_origin' (failed)\n")
        raise RuntimeError('worker failed')
    output = stream.getvalue()
    assert 'pelvis_origin' in output
    assert 'Processing stopped' in output
    assert '\x1b[?25h' in output  # Rich restores the cursor.


def test_redirected_progress_is_throttled_and_errors_are_kept(capsys):
    console = Console(file=StringIO(), force_terminal=False)
    with WorkerProgress('processing.log', console=console) as display:
        for frame in range(1, 223):
            display.feed(f'INFO mocap: Detecting and annotating {frame}/222 synchronized frames (running)\n')
        display.feed('INFO mocap: Triangulating observations (running)\n')
        display.feed('ERROR something else\n')
        display.feed('2026-09-29 ERROR visible failure\n')
    output = capsys.readouterr().out
    assert output.count('Detecting and annotating') == 2
    assert '222/222' in output
    assert 'visible failure' in output
    assert '\x1b' not in output


def test_terminal_retains_milestones_without_per_frame_lines(monkeypatch):
    from unittest.mock import Mock

    console = Console(file=StringIO(), force_terminal=True, width=120)
    printer = Mock(wraps=console.print)
    monkeypatch.setattr(console, 'print', printer)
    with WorkerProgress('processing.log', console=console) as display:
        display.feed('13:07:10 INFO calibration: Board detection in videos: 0/666 camera frames processed (3 cameras) (running)')
        for frame in range(1, 667):
            display.feed(f'13:07:11 INFO calibration: Board detection in videos: {frame}/666 camera frames processed (running)')
        display.feed('13:07:12 INFO calibration: Running anipose solver (running)')
        display.feed('13:07:13 INFO calibration:  (complete)')
        display.feed('13:07:13 INFO calibration:  (complete)')
    milestones = [call.args[0] for call in printer.call_args_list
                  if call.args and isinstance(call.args[0], str) and '[calibration]' in call.args[0]
                  and 'AVG' not in call.args[0]]
    averages = [call.args[0] for call in printer.call_args_list
                if call.args and isinstance(call.args[0], str) and '[calibration] AVG' in call.args[0]]
    assert len(averages) == 1
    assert 'FR/s' in averages[0] and 's/FR' in averages[0]
    assert len(milestones) == 4
    assert 'Stage |' in milestones[0]
    assert '0/666' not in milestones[0]
    assert '666/666' in milestones[1] and 'Stage ended' in milestones[1]
    assert 'Running anipose solver' in milestones[2]
    assert 'Complete' in milestones[3]
    assert milestones[0].startswith('13:07:10')


def test_history_uses_source_timestamps_and_identifies_sampled_counts(capsys):
    console = Console(file=StringIO(), force_terminal=False)
    with WorkerProgress('processing.log', console=console) as display:
        display.feed('2026-09-29 13:36:33,000 INFO calibration: Board detection in videos: 65/666 camera frames processed (running)')
        display.feed('2026-09-29 13:36:40,000 INFO calibration: Board detection in videos: 663/666 camera frames processed (running)')
        display.feed('2026-09-29 13:36:41,000 INFO calibration: Running anipose solver (running)')
        display.feed('2026-09-29 13:36:41,100 INFO Video processing summary: calibration / Cam1: 222 frames newly detected, 0 reused from observation cache; 222/222 frames read')
    output = capsys.readouterr().out
    assert '65/666' not in output
    assert '666 camera frames total' in output
    assert 'Last progress report:' in output and '663/666' in output
    assert 'reported interval 8.0s' in output
    assert '-' * 60 in output
    assert 'Video processing | measured results' not in output


def test_worker_identity_is_visible_without_native_progress_prefix(capsys):
    console = Console(file=StringIO(), force_terminal=False)
    with WorkerProgress('processing.log', console=console) as display:
        display.feed('Cam1: 6%|###| 13/222 2026-09-29 13:54:49,748 INFO Video processing start: Cam1; PID=48064, thread=1320; observation cache entries=0')
    output = capsys.readouterr().out
    assert 'PID=48064, thread=1320' in output
    assert 'observation cache entries=0' in output
    assert '13/222' not in output


def test_structured_residuals_preserve_units_and_missing_values(capsys):
    import json
    console = Console(file=StringIO(), force_terminal=False)
    with WorkerProgress('processing.log', console=console) as display:
        display.feed('INFO Processing statistics: ' + json.dumps({
            'stage': 'Triangulation residuals | Cam1',
            'values': {'Residual units': 'pixels', 'RMS reprojection error': 1.25,
                       'Maximum reprojection error': None}}))
    output = capsys.readouterr().out
    assert 'Triangulation residuals | Cam1' in output
    assert 'pixels' in output and '1.250' in output
    assert 'not available' in output


def test_rich_statistics_are_literal_and_persistent():
    stream = StringIO()
    console = Console(file=stream, force_terminal=True, width=120)
    with WorkerProgress('processing.log', console=console) as display:
        display.statistics('Stage [example]', {'Frames': 222, 'Cache hits': 0})
    assert 'Stage [example]' in stream.getvalue()
    assert 'Cache hits' in stream.getvalue()


def test_setup_transitions_never_create_statistics(monkeypatch):
    from unittest.mock import Mock
    with WorkerProgress('processing.log', console=Console(file=StringIO(), force_terminal=True)) as display:
        render = Mock()
        monkeypatch.setattr(display, 'numeric_table', render)
        display.feed('INFO calibration: Selecting calibration board (running)')
        display.feed('INFO calibration: Using 7x5 calibration board (running)')
        display.feed('INFO calibration: Saving calibration result (running)')
        display.feed('INFO calibration:  (complete)')
        render.assert_not_called()


def test_table_and_caption_use_one_console_write(monkeypatch):
    from unittest.mock import Mock
    console = Console(file=StringIO(), force_terminal=True, width=100)
    with WorkerProgress('processing.log', console=console) as display:
        printer = Mock(wraps=console.print)
        monkeypatch.setattr(console, 'print', printer)
        display.numeric_table('Results', ['Camera', 'N'], [['C1', 222]], 'caption stays with table')
        assert printer.call_count == 1


def test_camera_tables_are_grouped_despite_interleaved_stage_messages(monkeypatch):
    import json
    from unittest.mock import Mock
    with WorkerProgress('processing.log', console=Console(file=StringIO(), force_terminal=False)) as display:
        render = Mock()
        monkeypatch.setattr(display, 'numeric_table', render)
        for name in ('Cam2', 'Cam1', 'Cam3'):
            display.feed('INFO Processing statistics: ' + json.dumps(dict(
                stage='calibration | video processing', columns=['Fresh'], rows=[[222]], caption=name)))
            display.feed('INFO calibration: Running anipose solver (running)')
        render.assert_not_called()
        display.feed('INFO calibration:  (complete)')
        assert render.call_count == 1
        assert render.call_args.args[2] == [['C1', 222], ['C2', 222], ['C3', 222]]
        assert 'C1 = Cam1' in render.call_args.args[3]


def test_partial_camera_statistics_survive_failure(monkeypatch):
    import json
    from unittest.mock import Mock
    render = Mock()
    with pytest.raises(RuntimeError), WorkerProgress('processing.log', console=Console(file=StringIO(), force_terminal=False)) as display:
        monkeypatch.setattr(display, 'numeric_table', render)
        display.feed('INFO Processing statistics: ' + json.dumps(dict(
            stage='calibration | video processing', columns=['Fresh'], rows=[[10]], caption='Cam1')))
        raise RuntimeError('failure')
    assert render.call_count == 1
    assert render.call_args.args[2] == [['C1', 10]]


def test_distribution_statistics_include_spread_and_preserve_outliers():
    from freemocap.utilities.numerical_statistics import distribution_row
    row = distribution_row([1, 2, 3, 4, 100, float('nan'), float('inf')])
    assert row == pytest.approx([5, 100/7, 100/7, 22, 39.01281840626232, 1, 1.2, 3, 80.8, 100])
    assert distribution_row([]) == [0, *([None] * 9)]
    assert distribution_row([5]) == [1, 0, 0, 5, 0, 5, 5, 5, 5, 5]
    assert distribution_row([float('nan')]) == [0, 100, 0, *([None] * 7)]


def test_column_guide_precedes_table_and_distinguishes_queued_from_saved():
    stream = StringIO()
    console = Console(file=stream, force_terminal=True, width=140)
    with WorkerProgress('processing.log', console=console) as display:
        display.numeric_table('Video results', ['Fresh', 'Queued'], [[222, 222]])
    output = stream.getvalue()
    assert output.index('does not mean saved to disk') < output.index('222')
    assert 'Published' not in output


def test_execute_worker_retains_full_log_and_propagates_failure(tmp_path):
    import os
    import subprocess
    import sys
    from freemocap.tools.datasets.preparation import execute_worker

    log = tmp_path / 'processing.log'
    with pytest.raises(subprocess.CalledProcessError):
        execute_worker([sys.executable, '-B', '-c',
                        "print('internal detail'); print('INFO mocap: broken (failed)'); raise SystemExit(3)"],
                       environment=dict(os.environ), log_path=log, timeout=10.0)
    assert 'internal detail' in log.read_text()
    assert 'broken (failed)' in log.read_text()
