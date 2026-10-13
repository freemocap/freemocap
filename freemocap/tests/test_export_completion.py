"""Independent export destinations overlap; shared-manifest writers do not."""
from concurrent.futures import CancelledError
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock
import subprocess
import sys

import pytest

from freemocap.core.pipeline.posthoc.export_completion import complete_recording_exports
from freemocap.core.pipeline.performance_report import PerformanceReport
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.tests.test_wide_csv_export import scientific_recording  # noqa: F401


def make_request(structure):
    return SimpleNamespace(
        config=PosthocMocapPipelineConfig(exportToBlender=True, exportTallCsv=True,
            scientificExports=dict(formats=['npy'])),
        recording=SimpleNamespace(full_recording_path=structure.full_path),
        ipc=SimpleNamespace(should_continue=True), performance=PerformanceReport(),
        report=Mock(), report_export=Mock())


@pytest.mark.parametrize('scientific_fails', [False, True])
def test_export_overlap_independent_failure_and_shared_manifest_order(scientific_recording, monkeypatch, scientific_fails):
    structure, _ = scientific_recording
    request = make_request(structure)
    scientific_started, blender_started, scientific_finished = Event(), Event(), Event()
    output = SimpleNamespace(manifest_path=structure.exports_dir / 'metadata.json')

    def scientific(**kwargs):
        scientific_started.set()
        assert blender_started.wait(5), 'Blender must start before scientific files finish'
        scientific_finished.set()
        if scientific_fails:
            raise OSError('Disk full')
        return output

    def blender(**kwargs):
        blender_started.set()
        assert scientific_started.wait(5), 'Scientific files must start while Blender runs'
        return 'recording.blend'

    def tall(**kwargs):
        assert scientific_finished.is_set(), 'Shared manifest writers must be serialized'
        return output

    monkeypatch.setattr('freemocap.core.recording.exports.wide_csv.export_scientific', scientific)
    monkeypatch.setattr('freemocap.core.recording.exports.tall_csv.export_tall_csv', tall)
    monkeypatch.setattr('freemocap.core.blender.export_to_blender.export_to_blender', blender)
    if scientific_fails:
        with pytest.raises(RuntimeError, match='Disk full'):
            complete_recording_exports(request)
        request.report.assert_not_called()
    else:
        complete_recording_exports(request)
        assert request.report.call_args.args[0] == 'complete'
    states = {(call.args[0], call.args[2]) for call in request.report_export.call_args_list}
    assert ('blender', 'complete') in states
    assert ('tall_csv', 'complete') in states
    assert ('scientific_files', 'failed' if scientific_fails else 'complete') in states
    assert set(request.performance.snapshot()) == {
        'exports.total', 'export.scientific_files', 'export.tall_csv', 'export.blender'}


def test_cancelled_exports_are_joined_and_do_not_report_complete(scientific_recording, monkeypatch):
    structure, _ = scientific_recording
    request = make_request(structure)
    scientific_started, blender_stopped = Event(), Event()
    def scientific(**kwargs):
        scientific_started.set()
        assert blender_stopped.wait(5)
        raise CancelledError()
    def blender(**kwargs):
        assert scientific_started.wait(5)
        request.ipc.should_continue = False
        assert kwargs['cancelled']()
        blender_stopped.set()
        raise CancelledError()
    monkeypatch.setattr('freemocap.core.recording.exports.wide_csv.export_scientific', scientific)
    monkeypatch.setattr('freemocap.core.blender.export_to_blender.export_to_blender', blender)
    with pytest.raises(CancelledError):
        complete_recording_exports(request)
    request.report.assert_not_called()
    states = {(call.args[0], call.args[2]) for call in request.report_export.call_args_list}
    assert all((name, 'cancelled') in states for name in ('scientific_files', 'tall_csv', 'blender'))


def test_cancellable_subprocess_is_reaped(monkeypatch):
    from freemocap.core.blender import runtime
    processes = []
    original = runtime.start_external
    def start(*args, **kwargs):
        process = original(*args, **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(runtime, 'start_external', start)
    with pytest.raises(CancelledError):
        runtime.run_external([sys.executable, '-c', 'import time; time.sleep(60)'], timeout=10,
            cancelled=lambda: bool(processes), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert len(processes) == 1
    assert processes[0].poll() is not None
