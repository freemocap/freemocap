from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from freemocap.api.http.mocap.mocap_router import mocap_router


@pytest.fixture
def client():
    test_app = FastAPI()
    test_app.include_router(mocap_router)
    return TestClient(test_app)


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
