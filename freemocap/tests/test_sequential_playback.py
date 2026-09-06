"""Playback HTTP and posthoc reading share deterministic sequential video decoding."""

from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from freemocap.api.http.playback.playback_router import playback_router, video_readers, preferred_video_source, VideoSourceInfo, PlaybackVideoSource
from freemocap.core.pipeline.posthoc.video_group_helper import VideoHelper


@pytest.mark.parametrize("synchronized_available, expected", [(True, PlaybackVideoSource.SYNCHRONIZED), (False, PlaybackVideoSource.ANNOTATED)])
def test_playback_prefers_original_videos(synchronized_available: bool, expected: PlaybackVideoSource) -> None:
    assert preferred_video_source(
        synchronized=VideoSourceInfo(available=synchronized_available, valid=synchronized_available, video_count=int(synchronized_available)),
        annotated=VideoSourceInfo(available=True, valid=True, video_count=1),
    ) == expected


@pytest.fixture
def video_path(tmp_path: Path) -> Path:
    folder = tmp_path / "recording" / "synchronized_videos"
    folder.mkdir(parents=True)
    path = folder / "camera.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 30.0, (64, 48))
    if not writer.isOpened():
        raise RuntimeError("Unable to create fixture video")
    try:
        for frame in range(12):
            writer.write(np.full((48, 64, 3), frame * 20, dtype=np.uint8))
    finally:
        writer.release()
    return path


def test_posthoc_backward_read_after_cache_eviction(video_path: Path) -> None:
    helper = VideoHelper.from_video_path(video_path, cache_size_mb=0)
    try:
        for frame in (0, 10, 2, 11, 0):
            assert float(helper.read_frame_number(frame).mean()) == pytest.approx(frame * 20, abs=2)
    finally:
        helper.close()


def test_raw_media_and_sequential_frame_routes(video_path: Path, tmp_path: Path) -> None:
    app = FastAPI()
    app.include_router(playback_router)
    query = {"recording_parent_directory": str(tmp_path)}
    original_paths = set(tmp_path.rglob("*"))
    try:
        with TestClient(app) as client:
            media = client.get("/playback/recording/media", params=query)
            assert media.status_code == 200, media.text
            binding = media.json()[0]
            assert binding["video_filename"] == video_path.name
            assert set(tmp_path.rglob("*")) == original_paths
            assert binding["timeline"]["timestamps_s"] == pytest.approx([frame / 30 for frame in range(12)])
            for frame in (10, 2, 11):
                response = client.get(f"/playback/recording/videos/camera/frames/{frame}", params=query)
                assert response.status_code == 200, response.text
                image = cv2.imdecode(np.frombuffer(response.content, dtype=np.uint8), cv2.IMREAD_COLOR)
                assert float(image.mean()) == pytest.approx(frame * 20, abs=2)
            assert client.get("/playback/recording/videos/camera/frames/12", params=query).status_code == 422
    finally:
        video_readers.close()
