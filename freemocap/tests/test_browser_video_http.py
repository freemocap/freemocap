from io import BytesIO
from pathlib import Path

import av
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from freemocap.api.http.playback.playback_router import playback_router


@pytest.fixture
def recording(tmp_path: Path) -> Path:
    folder = tmp_path / "recording" / "synchronized_videos"
    folder.mkdir(parents=True)
    path = folder / "camera.mp4"
    with av.open(str(path), mode="w") as output:
        stream = output.add_stream("mpeg4", rate=30)
        stream.width = 160
        stream.height = 120
        stream.pix_fmt = "yuv420p"
        for index in range(60):
            frame = av.VideoFrame(width=160, height=120, format="yuv420p")
            for plane in frame.planes:
                plane.update(bytes([index + 40]) * plane.buffer_size)
            for packet in stream.encode(frame):
                output.mux(packet)
        for packet in stream.encode():
            output.mux(packet)
    return tmp_path


def test_browser_stream_http_and_invalid_start(recording: Path) -> None:
    app = FastAPI()
    app.include_router(playback_router)
    files = set(recording.rglob("*"))
    with TestClient(app) as client:
        params = dict(recording_parent_directory=str(recording), source="synchronized", start_seconds=0.5, duration_seconds=0.5)
        response = client.get("/playback/recording/videos/camera.mp4/browser", params=params)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        with av.open(BytesIO(response.content)) as output:
            assert len(list(output.decode(video=0))) == 15
        params["start_seconds"] = 100.0
        failed = client.get("/playback/recording/videos/camera.mp4/browser", params=params)
        assert failed.status_code == 422
        assert "beyond" in failed.json()["detail"]
    assert set(recording.rglob("*")) == files
