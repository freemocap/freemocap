import multiprocessing
import time
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry

import freemocap.api.http.mocap.mocap_router as mocap_router_module
from freemocap.api.http.mocap.mocap_router import mocap_router
from freemocap.core.pipeline.posthoc.sync_job_manager import SyncJobManager


@pytest.fixture
def client():
    test_app = FastAPI()
    test_app.include_router(mocap_router)
    return TestClient(test_app)


class _FakeApp:
    """Stand-in for FreemocapApplication exposing only what the sync endpoints need."""

    def __init__(self, sync_job_manager: SyncJobManager):
        self.sync_job_manager = sync_job_manager

    def create_sync_job(self, request):
        return self.sync_job_manager.create_job(request=request)


@pytest.fixture
def sync_app(monkeypatch):
    """Monkeypatches get_freemocap_app() to a lightweight fake backed by a real
    SyncJobManager (THREAD-mode worker registry — no real subprocess spawn, but
    still runs the actual skelly_synchronize pipeline in-process on a thread)."""
    global_kill_flag = multiprocessing.Value("b", False)
    registry = WorkerRegistry(global_kill_flag=global_kill_flag, worker_mode=WorkerMode.THREAD)
    manager = SyncJobManager(global_kill_flag=global_kill_flag, worker_registry=registry)
    fake_app = _FakeApp(sync_job_manager=manager)
    monkeypatch.setattr(mocap_router_module, "get_freemocap_app", lambda: fake_app)
    yield fake_app
    manager.shutdown()


def _make_video_file(tmp_path: Path, name: str, num_frames: int = 5) -> Path:
    """Write a small real video file so cv2 can read its frame count/fps."""
    video_path = tmp_path / name
    writer = cv2.VideoWriter(
        str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), 30.0, (16, 16)
    )
    for _ in range(num_frames):
        writer.write(np.zeros((16, 16, 3), dtype=np.uint8))
    writer.release()
    return video_path


def _make_flash_video_file(
    tmp_path: Path, name: str, dark_frames: int, bright_frames: int, fps: float = 30.0
) -> Path:
    """Write a video that's dark then abruptly bright — a synthetic brightness-sync flash."""
    video_path = tmp_path / name
    writer = cv2.VideoWriter(
        str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (16, 16)
    )
    for _ in range(dark_frames):
        writer.write(np.zeros((16, 16, 3), dtype=np.uint8))
    for _ in range(bright_frames):
        writer.write(np.full((16, 16, 3), 255, dtype=np.uint8))
    writer.release()
    return video_path


def _wait_for_sync_job(client: TestClient, job_id: str, timeout: float = 15.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get(f"/mocap/recording/synchronize/{job_id}")
        if response.status_code == 200:
            return response.json()
        if response.status_code not in (404, 425):
            pytest.fail(f"Sync job failed: {response.status_code} {response.json()}")
        time.sleep(0.1)
    pytest.fail("Sync job did not finish in time")


class TestImportVideos:
    def test_import_creates_recording_structure_and_copies_videos(self, tmp_path, client):
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        video_a = _make_video_file(source_dir, "cam0.mp4")
        video_b = _make_video_file(source_dir, "cam1.mp4")

        base_directory = tmp_path / "recordings"

        response = client.post("/mocap/recording/import", json={
            "videoPaths": [str(video_a), str(video_b)],
            "recordingName": "my_import_test",
            "baseDirectory": str(base_directory),
        })

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["recording_name"] == "my_import_test"
        assert body["video_count"] == 2

        recording_path = Path(body["recording_path"])
        synced_dir = recording_path / "synchronized_videos"
        assert (synced_dir / "cam0.mp4").is_file()
        assert (synced_dir / "cam1.mp4").is_file()
        assert (synced_dir / "cam0.mp4").read_bytes() == video_a.read_bytes()

        # Only the synchronized_videos folder should be created — no videos/annotated,
        # output, or logs scaffolding for a bare import.
        assert sorted(p.name for p in recording_path.iterdir()) == ["synchronized_videos"]

    def test_import_auto_generates_recording_name_when_omitted(self, tmp_path, client):
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        video_a = _make_video_file(source_dir, "only_cam.mp4")
        base_directory = tmp_path / "recordings"

        response = client.post("/mocap/recording/import", json={
            "videoPaths": [str(video_a)],
            "baseDirectory": str(base_directory),
        })

        assert response.status_code == 200
        body = response.json()
        assert "imported" in body["recording_name"]

    def test_import_rejects_empty_video_list(self, client):
        response = client.post("/mocap/recording/import", json={"videoPaths": []})
        assert response.status_code == 400

    def test_import_rejects_missing_video_file(self, tmp_path, client):
        base_directory = tmp_path / "recordings"
        response = client.post("/mocap/recording/import", json={
            "videoPaths": [str(tmp_path / "does_not_exist.mp4")],
            "baseDirectory": str(base_directory),
        })
        assert response.status_code == 400

    def test_import_rejects_unsynchronized_videos(self, tmp_path, client):
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        video_a = _make_video_file(source_dir, "cam0.mp4", num_frames=5)
        video_b = _make_video_file(source_dir, "cam1.mp4", num_frames=10)
        base_directory = tmp_path / "recordings"

        response = client.post("/mocap/recording/import", json={
            "videoPaths": [str(video_a), str(video_b)],
            "baseDirectory": str(base_directory),
        })

        assert response.status_code == 400
        assert not base_directory.exists()


class TestCheckVideoSync:
    def test_check_sync_reports_synchronized_when_frame_counts_match(self, tmp_path, client):
        video_a = _make_video_file(tmp_path, "cam0.mp4", num_frames=5)
        video_b = _make_video_file(tmp_path, "cam1.mp4", num_frames=5)

        response = client.post("/mocap/recording/check_sync", json={
            "videoPaths": [str(video_a), str(video_b)],
        })

        assert response.status_code == 200
        body = response.json()
        assert body["synchronized"] is True
        assert body["detail"] is None
        assert {v["frame_count"] for v in body["videos"]} == {5}

    def test_check_sync_reports_unsynchronized_when_frame_counts_differ(self, tmp_path, client):
        video_a = _make_video_file(tmp_path, "cam0.mp4", num_frames=5)
        video_b = _make_video_file(tmp_path, "cam1.mp4", num_frames=10)

        response = client.post("/mocap/recording/check_sync", json={
            "videoPaths": [str(video_a), str(video_b)],
        })

        assert response.status_code == 200
        body = response.json()
        assert body["synchronized"] is False
        assert body["detail"] is not None
        assert len(body["videos"]) == 2

    def test_check_sync_rejects_empty_video_list(self, client):
        response = client.post("/mocap/recording/check_sync", json={"videoPaths": []})
        assert response.status_code == 400

    def test_check_sync_rejects_missing_video_file(self, tmp_path, client):
        response = client.post("/mocap/recording/check_sync", json={
            "videoPaths": [str(tmp_path / "does_not_exist.mp4")],
        })
        assert response.status_code == 400


class TestSynchronizeVideos:
    def test_synchronize_rejects_empty_video_list(self, client, sync_app):
        response = client.post("/mocap/recording/synchronize", json={"videoPaths": []})
        assert response.status_code == 400

    def test_synchronize_rejects_missing_video_file(self, tmp_path, client, sync_app):
        response = client.post("/mocap/recording/synchronize", json={
            "videoPaths": [str(tmp_path / "does_not_exist.mp4")],
        })
        assert response.status_code == 400

    def test_get_synchronize_result_rejects_unknown_job(self, client, sync_app):
        response = client.get("/mocap/recording/synchronize/does-not-exist")
        assert response.status_code == 404

    def test_synchronize_then_import_brightness_method(self, tmp_path, client, sync_app):
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        # Different frame counts AND different flash offsets, so the sync step has
        # to both detect a real lag and trim to a shared frame count.
        video_a = _make_flash_video_file(source_dir, "cam0.mp4", dark_frames=10, bright_frames=10)
        video_b = _make_flash_video_file(source_dir, "cam1.mp4", dark_frames=13, bright_frames=10)

        start_response = client.post("/mocap/recording/synchronize", json={
            "videoPaths": [str(video_a), str(video_b)],
            "method": "brightness change detection",
        })
        assert start_response.status_code == 201
        job_id = start_response.json()["job_id"]

        result = _wait_for_sync_job(client, job_id)
        assert result["synchronized_frame_count"] is not None
        assert result["synchronized_frame_count"] > 0
        frame_counts_after = {video["frame_count"] for video in result["videos_after"]}
        assert len(frame_counts_after) == 1

        base_directory = tmp_path / "recordings"
        import_response = client.post("/mocap/recording/import", json={
            "videoPaths": [str(video_a), str(video_b)],
            "baseDirectory": str(base_directory),
            "syncJobId": job_id,
        })
        assert import_response.status_code == 200
        body = import_response.json()

        recording_path = Path(body["recording_path"])
        synced_dir = recording_path / "synchronized_videos"
        # Original basenames are preserved (not skelly_synchronize's "synced_" prefix).
        assert (synced_dir / "cam0.mp4").is_file()
        assert (synced_dir / "cam1.mp4").is_file()

        check_response = client.post("/mocap/recording/check_sync", json={
            "videoPaths": [str(synced_dir / "cam0.mp4"), str(synced_dir / "cam1.mp4")],
        })
        assert check_response.json()["synchronized"] is True

        # The job-local temp dir (raw/ + synchronized/) is cleaned up after import.
        job_tmp_dir = Path(result["synchronized_video_folder_path"]).parent
        assert not job_tmp_dir.exists()

        # And the completed job itself is no longer queryable.
        assert client.get(f"/mocap/recording/synchronize/{job_id}").status_code == 404
