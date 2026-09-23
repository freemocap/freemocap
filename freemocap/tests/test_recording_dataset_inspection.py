"""Decode actual small videos to verify dataset preflight rejects unusable inputs."""

from dataclasses import replace
import json

import av
import numpy as np
import pytest

from freemocap.tests.inspect_recording_datasets import inspect_recording, inspect_video
from freemocap.tests.recording_datasets import TEST_DATA


def write_video(path, count, rate=30):
    with av.open(str(path), mode="w") as container:
        stream = container.add_stream("libx264", rate=rate)
        stream.width, stream.height, stream.pix_fmt = 64, 48, "yuv420p"
        for index in range(count):
            frame = av.VideoFrame.from_ndarray(np.full((48, 64, 3), index * 20, dtype=np.uint8), format="bgr24")
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)


def recording(tmp_path, counts):
    folder = tmp_path / TEST_DATA.name / "synchronized_videos"
    folder.mkdir(parents=True)
    (folder.parent / "charuco_board_info.json").write_text(json.dumps({
        "square_size_mm": 58, "num_squares_height": 5, "num_squares_width": 7,
    }), encoding="utf-8")
    for index, count in enumerate(counts):
        write_video(folder / f"camera{index}.mp4", count)
    return folder


def test_decodes_timing_without_requiring_calibration_or_processed_data(tmp_path):
    recording(tmp_path, (4, 4, 4))
    report = inspect_recording(replace(TEST_DATA, expected_frame_count=4), recordings_root=tmp_path)
    assert report["calibration_files"] == report["parquet_files"] == report["timestamp_sidecars"] == []
    for video in report["videos"]:
        assert video["decoded_frames"] == 4
        assert (video["width"], video["height"]) == (64, 48)
        assert video["last_timestamp_s"] - video["first_timestamp_s"] == pytest.approx(3 / 30)
        assert video["minimum_interval_s"] == pytest.approx(1 / 30)
        assert video["maximum_interval_s"] == pytest.approx(1 / 30)


@pytest.mark.parametrize("counts, expected, message", [
    ((4, 4), 4, "three reference-camera"),
    ((4, 4, 3), 4, "frame counts disagree"),
    ((4, 4, 4), 222, "Expected 222 frames"),
])
def test_rejects_incomplete_recordings(tmp_path, counts, expected, message):
    recording(tmp_path, counts)
    with pytest.raises(ValueError, match=message):
        inspect_recording(replace(TEST_DATA, expected_frame_count=expected), recordings_root=tmp_path)


def test_rejects_undecodable_video(tmp_path):
    path = tmp_path / "broken.mp4"
    path.write_bytes(b"not a video")
    with pytest.raises(av.error.InvalidDataError):
        inspect_video(path)


def test_rejects_camera_timeline_mismatch(tmp_path):
    folder = recording(tmp_path, (4, 4, 4))
    write_video(folder / "camera2.mp4", 4, rate=24)
    with pytest.raises(ValueError, match="presentation timelines disagree"):
        inspect_recording(replace(TEST_DATA, expected_frame_count=4), recordings_root=tmp_path)


@pytest.mark.parametrize("board", [None, {"square_size_mm": 1}, {
    "square_size_mm": 58, "num_squares_height": 7, "num_squares_width": 5,
}])
def test_rejects_missing_or_incompatible_board_metadata(tmp_path, board):
    folder = recording(tmp_path, (4, 4, 4))
    path = folder.parent / "charuco_board_info.json"
    if board is None:
        path.unlink()
    else:
        path.write_text(json.dumps(board), encoding="utf-8")
    with pytest.raises(ValueError, match="7x5 board metadata"):
        inspect_recording(replace(TEST_DATA, expected_frame_count=4), recordings_root=tmp_path)
