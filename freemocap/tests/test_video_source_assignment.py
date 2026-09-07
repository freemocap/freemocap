"""File labels and declared source associations remain distinct from physical camera identity."""

from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from freemocap.core.pipeline.posthoc.video_group_helper import VideoGroupHelper


def write_video(*, path: Path, frame_count: int = 2) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 30.0, (64, 48))
    assert writer.isOpened()
    try:
        for _ in range(frame_count):
            writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
    finally:
        writer.release()


def test_arbitrary_names_do_not_infer_camera_ids_or_order(tmp_path: Path) -> None:
    paths = [tmp_path / name for name in ("capture.id-abcd.idx-9.avi", "holiday camera two.avi")]
    for path in paths:
        write_video(path=path)
    group = VideoGroupHelper.from_video_paths(video_paths=paths)
    try:
        assert group.camera_ids == [path.name for path in paths]
        assert group.frame_count == 2
        assert all(group.video_metadata_by_id[source] is video.metadata for source, video in group.videos.items())
    finally:
        group.close()


def test_declared_sources_override_filename_semantics(tmp_path: Path) -> None:
    path = tmp_path / "capture.id-wrong.idx-99.avi"
    write_video(path=path)
    group = VideoGroupHelper.from_manifest_videos(manifest_videos={"declared": path.name}, videos_dir=tmp_path)
    try:
        assert group.camera_ids == ["declared"]
        assert group.video_metadata_by_id["declared"].file_path == path
    finally:
        group.close()


def test_duplicate_filenames_fail_before_opening_readers(tmp_path: Path) -> None:
    paths: list[Path] = []
    for name in ("first", "second"):
        folder = tmp_path / name
        folder.mkdir()
        path = folder / "clip.avi"
        path.touch()
        paths.append(path)
    with patch("freemocap.core.pipeline.posthoc.video_group_helper.VideoHelper.from_video_path") as reader:
        with pytest.raises(ValueError, match="Duplicate video filenames"):
            VideoGroupHelper.from_video_paths(video_paths=paths)
        reader.assert_not_called()


def test_duplicate_file_associations_fail_before_opening_readers(tmp_path: Path) -> None:
    path = tmp_path / "clip.avi"
    path.touch()
    with patch("freemocap.core.pipeline.posthoc.video_group_helper.VideoHelper.from_video_path") as reader:
        with pytest.raises(ValueError, match="same video file"):
            VideoGroupHelper.from_source_paths(source_paths={"first": path, "second": path})
        reader.assert_not_called()


def test_unequal_frame_counts_close_every_reader(tmp_path: Path) -> None:
    paths = [tmp_path / "first.avi", tmp_path / "second.avi"]
    for frame_count, path in enumerate(paths, start=2):
        write_video(path=path, frame_count=frame_count)
    with pytest.raises(ValueError, match="same frame count"):
        VideoGroupHelper.from_video_paths(video_paths=paths)
    for path in paths:
        path.unlink()
