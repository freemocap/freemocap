"""Tests for the realtime CharucoRecorderNode write side.

The recorder must persist observations keyed by CONNECTION frame number — the
stable identifier shared with the recording's per-camera timestamps CSV — so that
realtime frames the pipeline dropped leave GAPS rather than shifting every later
observation onto the wrong recorded video frame. (Keying by arrival order was the
original defect: it silently mis-aligned the cache to the calibration videos.)
"""
import pickle
from pathlib import Path

import cv2
import numpy as np
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.trackers.charuco_tracker.charuco_board_definition import CharucoBoardDefinition
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.core.pipeline.realtime.charuco_recorder_node import (
    CACHE_FILENAME,
    _flush_buffer,
)


# ---------------------------------------------------------------------------
# Helpers: build real CharucoObservations
# ---------------------------------------------------------------------------

def _board_observation_data(board_def: CharucoBoardDefinition) -> dict:
    charuco_board = cv2.aruco.CharucoBoard(
        size=(board_def.squares_x, board_def.squares_y),
        squareLength=board_def.square_length_mm,
        markerLength=board_def.aruco_marker_length_mm,
        dictionary=board_def.aruco_dictionary,
    )
    return {
        "all_charuco_ids": list(range(board_def.n_corners)),
        "all_charuco_corners_in_object_coordinates": board_def.corner_positions_board_frame.astype(np.float32),
        "all_aruco_ids": [int(i) for i in charuco_board.getIds()],
        "all_aruco_corners_in_object_coordinates": np.array(charuco_board.getObjPoints(), dtype=np.float32),
    }


def make_detected_charuco_observation(frame_number: int = 0) -> CharucoObservation:
    board_def = CharucoBoardDefinition.create_test_data_7x5()
    obs_data = _board_observation_data(board_def)
    charuco_corners = np.array(
        [[[100.0, 200.0]], [[150.0, 200.0]], [[200.0, 200.0]], [[250.0, 200.0]]],
        dtype=np.float32,
    )
    charuco_ids = np.array([0, 1, 2, 3], dtype=np.int32).reshape(-1, 1)
    marker_corners_list = [
        np.array([[[0.0, 0.0]], [[10.0, 0.0]], [[10.0, 10.0]], [[0.0, 10.0]]], dtype=np.float32)
    ]
    marker_ids = np.array([obs_data["all_aruco_ids"][0]], dtype=np.int32).reshape(-1, 1)
    return CharucoObservation.from_detection_results(
        frame_number=frame_number,
        detected_charuco_corners=charuco_corners,
        detected_charuco_corner_ids=charuco_ids,
        detected_aruco_marker_corners=marker_corners_list,
        detected_aruco_marker_ids=marker_ids,
        image_size=(1920, 1080),
        **obs_data,
    )


def make_empty_charuco_observation(frame_number: int = 0) -> CharucoObservation:
    board_def = CharucoBoardDefinition.create_test_data_7x5()
    obs_data = _board_observation_data(board_def)
    return CharucoObservation.from_detection_results(
        frame_number=frame_number,
        detected_charuco_corners=None,
        detected_charuco_corner_ids=None,
        detected_aruco_marker_corners=None,
        detected_aruco_marker_ids=None,
        image_size=(1920, 1080),
        **obs_data,
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
        assert observations["cam_0"][13].charuco_empty
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
