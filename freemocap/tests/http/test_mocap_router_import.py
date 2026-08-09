from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from freemocap.api.http.mocap.mocap_router import mocap_router


@pytest.fixture
def client():
    test_app = FastAPI()
    test_app.include_router(mocap_router)
    return TestClient(test_app)


def _make_video_file(tmp_path: Path, name: str) -> Path:
    video_path = tmp_path / name
    video_path.write_bytes(b"not-a-real-video")
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
        assert (synced_dir / "cam0.mp4").read_bytes() == b"not-a-real-video"

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
