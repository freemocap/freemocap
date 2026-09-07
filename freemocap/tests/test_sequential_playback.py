"""Playback serves media bytes; posthoc readers provide deterministic frame access."""

from pathlib import Path
from shutil import copyfile

from skellycam.core.recorders.videos.pyav_video_writer import PyavVideoWriter
from skellycam.core.recorders.videos.video_derivation import VideoDerivation
import cv2
import numpy as np
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from freemocap.api.http.playback.playback_router import playback_router, _validate_video_source, preferred_video_source, VideoSourceInfo, PlaybackVideoSource
from freemocap.core.pipeline.posthoc.video_group_helper import VideoHelper


def test_annotations_inherit_inferred_source_timing(video_path: Path, tmp_path: Path) -> None:
    annotated = video_path.parent.parent / "annotated_videos" / "camera_annotated.avi"
    annotated.parent.mkdir()
    writer = PyavVideoWriter(path=str(annotated), fps=30.0, width=64, height=48)
    writer.set_container_metadata(metadata=VideoDerivation(source_video="synchronized_videos/camera.avi", frame_count=12).to_container_metadata())
    try:
        for _ in range(12):
            writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
    finally:
        writer.release()
    app = FastAPI()
    app.include_router(playback_router)
    with TestClient(app) as client:
        response = client.get("/playback/recording/media", params={"recording_parent_directory": str(tmp_path)})
    assert response.status_code == 200, response.text
    original, overlay = response.json()
    assert overlay["video_filename"] == annotated.name
    assert overlay["timeline"] == original["timeline"]
    assert overlay["timeline"]["timestamps_s"][-1] == pytest.approx(11 / 30)


@pytest.mark.parametrize("annotated_available, expected", [(True, PlaybackVideoSource.ANNOTATED), (False, PlaybackVideoSource.SYNCHRONIZED)])
def test_playback_prefers_annotated_videos(annotated_available: bool, expected: PlaybackVideoSource) -> None:
    assert preferred_video_source(
        synchronized=VideoSourceInfo(available=True, valid=True, video_count=1),
        annotated=VideoSourceInfo(available=annotated_available, valid=annotated_available, video_count=int(annotated_available)),
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


@pytest.mark.parametrize("source", ["synchronized", "annotated"])
def test_playback_serves_video_bytes(video_path: Path, tmp_path: Path, source: str) -> None:
    if source == "annotated":
        folder = video_path.parent.parent / "annotated_videos"
        folder.mkdir()
        copyfile(src=video_path, dst=folder / video_path.name)
    app = FastAPI()
    app.include_router(playback_router)
    query = {"recording_parent_directory": str(tmp_path), "source": source}
    with TestClient(app) as client:
        response = client.get("/playback/recording/videos/camera.avi", params=query, headers={"Range": "bytes=0-127"})
        assert response.status_code == 206, response.text
        assert response.content == video_path.read_bytes()[:128]
        assert client.get("/playback/recording/videos/camera.avi/frames/0", params=query).status_code == 404


def test_media_inspection_does_not_infer_camera_identity(video_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_identity(*args: object, **kwargs: object) -> None:
        raise AssertionError("Media inspection must not infer camera identity")

    monkeypatch.setattr("skellycam.core.recorders.videos.video_filename.VideoFilename.from_camera_config", reject_identity)
    folder = video_path.parent.parent / "annotated_videos"
    folder.mkdir()
    for name in ("a date 2026-09-06_annotated.avi", "arbitrary subject.avi"):
        copyfile(src=video_path, dst=folder / name)
    result = _validate_video_source(recording_path=video_path.parent.parent, source_name="annotated", recording_id="recording")
    assert result.valid
    assert result.video_count == 2
    (folder / "broken.avi").write_bytes(b"invalid video")
    with pytest.raises(HTTPException, match="broken.avi"):
        _validate_video_source(recording_path=video_path.parent.parent, source_name="annotated", recording_id="recording")
