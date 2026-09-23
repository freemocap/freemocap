"""Preparation must distinguish successful tasks and intact results from stale files."""

import json
import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from freemocap.tests.prepare_recording_dataset import execute_worker, file_digest, reuse_recording, wait_for_success


@pytest.mark.parametrize("status", ["running", "failed", "cancelled"])
def test_stopped_worker_is_not_success(status):
    task = SimpleNamespace(status=status, task_type="mocap", progress=SimpleNamespace(detail="stopped"))
    manager = SimpleNamespace(refresh_progress=lambda: None, registry=SimpleNamespace(tasks={"task": task}), pipelines={})
    with pytest.raises(RuntimeError):
        wait_for_success(manager, SimpleNamespace(id="task"), timeout=1.0)


def test_success_requires_terminal_state_and_worker_cleanup():
    task = Mock(status="complete", task_type="mocap", progress=SimpleNamespace(detail="done"))
    task.model_dump.return_value = {"status": "complete"}
    manager = SimpleNamespace(registry=SimpleNamespace(tasks={"task": task}), pipelines={"task": object()})
    manager.refresh_progress = lambda: manager.pipelines.clear()
    assert wait_for_success(manager, SimpleNamespace(id="task"), timeout=1.0) == {"status": "complete"}


def test_partial_attempt_without_ready_marker_is_not_reused(tmp_path):
    (tmp_path / "partial.parquet").write_bytes(b"unfinished")
    assert reuse_recording(tmp_path, {"version": 1}) is None


def ready_recording(root):
    recording = root / "attempt" / "recording"
    recording.mkdir(parents=True)
    parquet = recording / "recording_data.parquet"
    calibration = recording / "calibration.toml"
    parquet.write_bytes(b"validated output")
    calibration.write_bytes(b"validated calibration")
    ready = {"identity": {"version": 1}, "recording": str(recording), "result": {
        "validation": {"parquet_sha256": file_digest(parquet)},
        "calibration_filename": calibration.name, "calibration_sha256": file_digest(calibration),
    }}
    (root / "ready.json").write_text(json.dumps(ready), encoding="utf-8")
    return recording


def test_reuse_requires_matching_preparation_identity(tmp_path):
    recording = ready_recording(tmp_path)
    assert reuse_recording(tmp_path, {"version": 1}) == recording
    assert reuse_recording(tmp_path, {"version": 2}) is None


@pytest.mark.parametrize("filename", ["recording_data.parquet", "calibration.toml"])
def test_changed_results_cannot_be_reused(tmp_path, filename):
    recording = ready_recording(tmp_path)
    (recording / filename).write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed or is missing"):
        reuse_recording(tmp_path, {"version": 1})


def test_worker_relay_preserves_unicode_and_reports_failure(tmp_path):
    log = tmp_path / "worker.log"
    command = [sys.executable, "-c", "print('mocap: \\u258d', flush=True); raise SystemExit(2)"]
    with pytest.raises(subprocess.CalledProcessError):
        execute_worker(command, environment=dict(os.environ, PYTHONUTF8="1"), log_path=log, timeout=10.0)
    assert "mocap: \u258d" in log.read_text(encoding="utf-8")
