"""Preparation must distinguish successful tasks and intact results from stale files."""

import json
import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from freemocap.tests.prepare_recording_dataset import execute_worker, file_digest, reuse_recording, wait_for_success
from freemocap.tests import prepare_recording_dataset as preparation
from freemocap.tests.recording_datasets import TEST_DATA


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


@pytest.fixture
def lifecycle(tmp_path, monkeypatch):
    raw = tmp_path / "raw" / TEST_DATA.name
    videos = raw / "synchronized_videos"
    videos.mkdir(parents=True)
    video = videos / "camera.mp4"
    video.write_bytes(b"original input")
    (raw / "charuco_board_info.json").write_text("{}")
    report = {"videos": [{"filename": video.name, "sha256": file_digest(video),
                           "decoded_frames": 222, "nominal_fps": 6.0}]}
    monkeypatch.setattr(preparation, "acquire_recording", lambda *a, **kw: raw)
    monkeypatch.setattr(preparation, "inspect_recording", lambda *a, **kw: report)
    monkeypatch.setattr(preparation, "software_identity", lambda: {"revision": "first"})
    monkeypatch.setattr(preparation, "validate_parquet", lambda *a, **kw: {})
    calls = []

    def worker(command, *, environment, log_path, timeout):
        from pathlib import Path
        request = json.loads(Path(command[-1]).read_text())
        recording = Path(request["recording"])
        assert not (recording / f"{recording.name}_data.parquet").exists()
        calls.append(recording)
        parquet = recording / f"{recording.name}_data.parquet"
        parquet.write_bytes(b"new output")
        calibration = recording / "calibration.toml"
        calibration.write_bytes(b"new calibration")
        result = {"validation": {"parquet_sha256": file_digest(parquet)},
                  "calibration_filename": calibration.name, "calibration_sha256": file_digest(calibration)}
        (log_path.parent / "result.json").write_text(json.dumps(result))
        log_path.write_text("finished")

    monkeypatch.setattr(preparation, "execute_worker", worker)
    args = dict(recordings_root=raw.parent, prepared_root=tmp_path / "testing" / "prepared", timeout=1.0)
    return args, calls, raw


def test_stable_results_survive_fresh_runs_and_software_changes(lifecycle, monkeypatch):
    args, calls, raw = lifecycle
    current = preparation.prepare(TEST_DATA, fresh=False, **args)
    parquet = current / f"{current.name}_data.parquet"
    before = (file_digest(parquet), parquet.stat().st_mtime_ns)
    monkeypatch.setattr(preparation, "software_identity", lambda: {"revision": "new"})
    assert preparation.prepare(TEST_DATA, fresh=False, **args) == current
    assert len(calls) == 1
    assert preparation.prepare(TEST_DATA, fresh=True, **args) == current
    assert len(calls) == 2
    assert before == (file_digest(parquet), parquet.stat().st_mtime_ns)
    assert not (args["prepared_root"] / TEST_DATA.name / "scratch").exists()
    assert (raw / "synchronized_videos" / "camera.mp4").read_bytes() == b"original input"
    assert (args["prepared_root"].parent / preparation.WARNING_FILENAME).is_file()


def test_failure_preserves_prepared_data_and_next_run_removes_stale_outputs(lifecycle, monkeypatch):
    args, calls, raw = lifecycle
    current = preparation.prepare(TEST_DATA, fresh=False, **args)
    worker = preparation.execute_worker

    def fail(command, *, environment, log_path, timeout):
        worker(command, environment=environment, log_path=log_path, timeout=timeout)
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(preparation, "execute_worker", fail)
    with pytest.raises(subprocess.CalledProcessError):
        preparation.prepare(TEST_DATA, fresh=True, **args)
    scratch = args["prepared_root"] / TEST_DATA.name / "scratch"
    assert (scratch / "result.json").exists()
    assert preparation.prepare(TEST_DATA, fresh=False, **args) == current
    monkeypatch.setattr(preparation, "execute_worker", worker)
    preparation.prepare(TEST_DATA, fresh=True, **args)
    assert not scratch.exists()


def test_preparation_rejects_output_inside_original_recordings(lifecycle):
    args, calls, raw = lifecycle
    args["prepared_root"] = raw.parent
    with pytest.raises(ValueError, match="separate"):
        preparation.prepare(TEST_DATA, fresh=False, **args)
    assert not calls


def test_cleanup_does_not_touch_neighboring_prepared_files(tmp_path):
    (tmp_path / "current").mkdir()
    retained = tmp_path / "current" / "data.parquet"
    retained.write_bytes(b"keep")
    (tmp_path / "scratch").mkdir()
    (tmp_path / "scratch" / "stale.parquet").write_bytes(b"delete")
    preparation.remove_scratch(tmp_path)
    assert retained.read_bytes() == b"keep"
    assert not (tmp_path / "scratch").exists()


def test_active_run_blocks_scratch_cleanup(lifecycle, monkeypatch):
    from filelock import FileLock, Timeout
    args, calls, raw = lifecycle
    preparation.prepare(TEST_DATA, fresh=False, **args)
    root = args["prepared_root"] / TEST_DATA.name
    scratch = root / "scratch"
    scratch.mkdir()
    sentinel = scratch / "active.txt"
    sentinel.write_text("in use")
    with FileLock(str(root / "prepare.lock"), timeout=0):
        monkeypatch.setattr(preparation, "FileLock", lambda path, **kwargs: FileLock(path, timeout=0))
        with pytest.raises(Timeout):
            preparation.prepare(TEST_DATA, fresh=True, **args)
    assert sentinel.read_text() == "in use"
    assert len(calls) == 1


def test_cleanup_rejects_link_before_deleting_any_files(tmp_path, monkeypatch):
    from pathlib import Path
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    sentinel = scratch / "linked"
    sentinel.write_text("keep")
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == sentinel or original(path))
    with pytest.raises(ValueError, match="filesystem link"):
        preparation.remove_scratch(tmp_path)
    assert sentinel.read_text() == "keep"


def test_adopts_previous_layout_without_processing(lifecycle):
    args, calls, raw = lifecycle
    current = preparation.prepare(TEST_DATA, fresh=False, **args)
    root = args["prepared_root"] / TEST_DATA.name
    legacy = root / "0123456789abcdef"
    previous = legacy / "attempt" / "recordings" / TEST_DATA.name
    previous.parent.mkdir(parents=True)
    current.rename(previous)
    ready = json.loads((root / "ready.json").read_text())
    ready["recording"] = str(previous)
    (legacy / "ready.json").write_text(json.dumps(ready))
    (root / "ready.json").unlink()
    assert preparation.prepare(TEST_DATA, fresh=False, **args) == current
    assert len(calls) == 1
    assert not previous.exists()
