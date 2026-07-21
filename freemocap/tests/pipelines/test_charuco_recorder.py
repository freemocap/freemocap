"""Tests for the realtime CharucoRecorderNode write side.

The recorder must persist observations keyed by CONNECTION frame number — the
stable identifier shared with the recording's per-camera timestamps CSV — so that
realtime frames the pipeline dropped leave GAPS rather than shifting every later
observation onto the wrong recorded video frame. (Keying by arrival order was the
original defect: it silently mis-aligned the cache to the calibration videos.)
"""
import pickle
from pathlib import Path

import numpy as np
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellytracker.core.data_primitives.observation import Observation, StageObservation
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition

from freemocap.core.pipeline.realtime.charuco_recorder_node import (
    CACHE_FILENAME,
    _flush_buffer,
)


# ---------------------------------------------------------------------------
# Helpers: build real Observations for a "charuco" stage
# ---------------------------------------------------------------------------

_CHARUCO_CORNER_NAMES = tuple(f"CharucoCorner-{i}" for i in range(4))


def make_detected_charuco_observation(frame_number: int = 0) -> Observation:
    xyz = np.array(
        [[100.0, 200.0, 0.0], [150.0, 200.0, 0.0], [200.0, 200.0, 0.0], [250.0, 200.0, 0.0]],
        dtype=np.float64,
    )
    visibility = np.ones(4, dtype=np.float64)
    keypoints = Keypoints(names=_CHARUCO_CORNER_NAMES, xyz=xyz, visibility=visibility)
    return Observation(
        frame_number=frame_number,
        image_size=(1080, 1920),
        stages={"charuco": StageObservation(name="charuco", keypoints=keypoints)},
    )


def make_empty_charuco_observation(frame_number: int = 0) -> Observation:
    xyz = np.full((4, 3), np.nan, dtype=np.float64)
    visibility = np.zeros(4, dtype=np.float64)
    keypoints = Keypoints(names=_CHARUCO_CORNER_NAMES, xyz=xyz, visibility=visibility)
    return Observation(
        frame_number=frame_number,
        image_size=(1080, 1920),
        stages={"charuco": StageObservation(name="charuco", keypoints=keypoints)},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCharucoRecorderFlush:
    def test_module_imports(self):
        assert CACHE_FILENAME == "charuco_observations_realtime.pkl"
        assert callable(_flush_buffer)

    def test_flush_keys_observations_by_connection_frame(self, tmp_path):
        """The flushed cache must be keyed by connection frame number, per camera,
        with gaps for dropped frames — NOT a positional list."""
        board = CharucoBoardDefinition.create_test_data_7x5()
        # cam_0 saw connection frames 10, 12, 13 (dropped 11);
        # cam_1 saw 10, 11 (dropped 12, 13) — a DIFFERENT drop pattern per camera.
        buffer = {
            "cam_0": {
                10: make_detected_charuco_observation(10),
                12: make_detected_charuco_observation(12),
                13: make_empty_charuco_observation(13),
            },
            "cam_1": {
                10: make_detected_charuco_observation(10),
                11: make_detected_charuco_observation(11),
            },
        }
        recording_info = RecordingInfo(
            recording_directory=str(tmp_path), recording_name="rec", mic_device_index=-1,
        )

        _flush_buffer(buffer=buffer, recording_info=recording_info, board_config=board)

        cache_path = Path(recording_info.full_recording_path) / "output_data" / CACHE_FILENAME
        assert cache_path.exists()
        with open(cache_path, "rb") as f:
            data = pickle.load(f)

        observations = data["observations"]
        # Keyed by connection frame number (dict), gaps preserved.
        assert isinstance(observations["cam_0"], dict)
        assert set(observations["cam_0"].keys()) == {10, 12, 13}
        assert set(observations["cam_1"].keys()) == {10, 11}
        # The object at a key is the observation captured at THAT connection frame.
        assert observations["cam_0"][10].frame_number == 10
        assert np.isnan(observations["cam_0"][13].stages["charuco"].keypoints.xyz).all()
        # Board round-trips; frame_range is the min/max connection number seen.
        assert data["board_definition"].squares_x == board.squares_x
        assert data["frame_range"] == (10, 13)

    def test_flush_empty_buffer_writes_empty_cache(self, tmp_path):
        board = CharucoBoardDefinition.create_test_data_7x5()
        recording_info = RecordingInfo(
            recording_directory=str(tmp_path), recording_name="rec", mic_device_index=-1,
        )

        _flush_buffer(buffer={"cam_0": {}, "cam_1": {}}, recording_info=recording_info, board_config=board)

        cache_path = Path(recording_info.full_recording_path) / "output_data" / CACHE_FILENAME
        assert cache_path.exists()
        with open(cache_path, "rb") as f:
            data = pickle.load(f)
        assert data["observations"] == {"cam_0": {}, "cam_1": {}}
        assert data["frame_range"] == (0, 0)
