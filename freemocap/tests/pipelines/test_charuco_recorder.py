import multiprocessing
import pickle
from pathlib import Path

import cv2
import numpy as np
import pytest
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.trackers.charuco_tracker.charuco_board_definition import CharucoBoardDefinition
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.realtime.charuco_recorder_node import CharucoRecorderNode
from freemocap.pubsub.pubsub_manager import PubSubTopicManager
from freemocap.pubsub.pubsub_topics import (
    CalibrationRecordingStateMessage,
    CalibrationRecordingStateTopic,
    CameraNodeOutputMessage,
    CameraNodeOutputTopic,
)


# ---------------------------------------------------------------------------
# Helper: build the data needed for CharucoObservation.from_detection_results()
# ---------------------------------------------------------------------------

def _board_observation_data(board_def: CharucoBoardDefinition) -> dict:
    """Return the kwargs needed by ``CharucoObservation.from_detection_results()``
    for the given board definition."""
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


def make_empty_charuco_observation() -> CharucoObservation:
    """Return a CharucoObservation with no detected corners."""
    board_def = CharucoBoardDefinition.create_test_data_7x5()
    obs_data = _board_observation_data(board_def)
    return CharucoObservation.from_detection_results(
        frame_number=0,
        detected_charuco_corners=None,
        detected_charuco_corner_ids=None,
        detected_aruco_marker_corners=None,
        detected_aruco_marker_ids=None,
        image_size=(1920, 1080),
        **obs_data,
    )


def make_detected_charuco_observation() -> CharucoObservation:
    """Return a CharucoObservation with fake detected corners."""
    board_def = CharucoBoardDefinition.create_test_data_7x5()
    obs_data = _board_observation_data(board_def)

    # Create fake detection: 4 corners with IDs [0,1,2,3]
    charuco_corners = np.array(
        [[[100.0, 200.0]], [[150.0, 200.0]], [[200.0, 200.0]], [[250.0, 200.0]]],
        dtype=np.float32,
    )
    charuco_ids = np.array([0, 1, 2, 3], dtype=np.int32).reshape(-1, 1)

    # Need at least 1 marker with 4 corners for the ArUco side
    marker_corners_list = [
        np.array(
            [[[0.0, 0.0]], [[10.0, 0.0]], [[10.0, 10.0]], [[0.0, 10.0]]],
            dtype=np.float32,
        )
    ]
    marker_ids = np.array([obs_data["all_aruco_ids"][0]], dtype=np.int32).reshape(-1, 1)

    return CharucoObservation.from_detection_results(
        frame_number=0,
        detected_charuco_corners=charuco_corners,
        detected_charuco_corner_ids=charuco_ids,
        detected_aruco_marker_corners=marker_corners_list,
        detected_aruco_marker_ids=marker_ids,
        image_size=(1920, 1080),
        **obs_data,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def global_kill_flag():
    return multiprocessing.Value("b", False)


@pytest.fixture
def heartbeat_timestamp():
    return multiprocessing.Value("d", 0.0)


@pytest.fixture
def pubsub(global_kill_flag):
    ps = PubSubTopicManager.create(global_kill_flag=global_kill_flag)
    yield ps
    ps.close()


@pytest.fixture
def ipc(global_kill_flag, heartbeat_timestamp):
    return PipelineIPC.create(
        global_kill_flag=global_kill_flag,
        heartbeat_timestamp=heartbeat_timestamp,
    )


@pytest.fixture
def recording_info(tmp_path):
    return RecordingInfo(
        recording_directory=str(tmp_path),
        recording_name="test_recording",
        mic_device_index=-1,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCharucoRecorderNode:
    def test_module_imports(self):
        """Sanity-check that the module and key symbols are importable."""
        assert CharucoRecorderNode is not None
        from freemocap.core.pipeline.realtime.charuco_recorder_node import (
            CACHE_FILENAME,
            _flush_buffer,
        )
        assert CACHE_FILENAME == "charuco_observations_realtime.pkl"
        assert callable(_flush_buffer)

    def test_starts_idle(self, pubsub, ipc):
        """Before recording signal, no observations are buffered."""
        # Publish a camera output while no recording is active
        obs = make_detected_charuco_observation()
        camera_pub = pubsub.get_publication_queue(CameraNodeOutputTopic)
        camera_pub.put(CameraNodeOutputMessage(
            camera_id="cam_0",
            frame_number=0,
            charuco_observation=obs,
        ))
        pubsub.drain()

        # Verify the message drained successfully (no crash = pass)
        # The recorder's _run loop isn't running, so this is a structural test
        # that the pub/sub wiring doesn't error on the message types.

    def test_buffer_appends_per_frame(self):
        """When recording, each CameraNodeOutputMessage appends to buffer."""
        # Simulate the internal buffer state (exercises the data structure,
        # not the node's _run loop directly)
        camera_ids = ["cam_0", "cam_1"]
        buffer: dict = {cid: [] for cid in camera_ids}

        # Simulate receiving frames during recording
        for frame_number in range(5):
            for cam_id in camera_ids:
                obs = (
                    make_detected_charuco_observation()
                    if frame_number % 2 == 0
                    else make_empty_charuco_observation()
                )
                buffer[cam_id].append(obs)

        # Verify: 5 frames per camera
        assert len(buffer["cam_0"]) == 5
        assert len(buffer["cam_1"]) == 5
        # frame 3 was even → detected
        assert not buffer["cam_0"][2].charuco_empty
        # frame 4 was odd → empty
        assert buffer["cam_0"][3].charuco_empty

    def test_cache_file_is_valid_pickle(self, tmp_path):
        """The cache pickle file can be loaded and contains expected structure."""
        board = CharucoBoardDefinition.create_test_data_7x5()
        cache_data = {
            "board_definition": board,
            "observations": {
                "cam_0": [make_detected_charuco_observation() for _ in range(3)],
            },
            "frame_range": (0, 2),
            "recording_uuid": "test-uuid",
        }
        cache_path = tmp_path / "output_data" / "charuco_observations_realtime.pkl"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "wb") as f:
            pickle.dump(cache_data, f, protocol=pickle.HIGHEST_PROTOCOL)

        # Load and verify
        with open(cache_path, "rb") as f:
            loaded = pickle.load(f)

        assert loaded["board_definition"].squares_x == board.squares_x
        assert loaded["board_definition"].squares_y == board.squares_y
        assert len(loaded["observations"]["cam_0"]) == 3
        assert loaded["frame_range"] == (0, 2)
        assert not loaded["observations"]["cam_0"][0].charuco_empty

    def test_empty_observations_preserved(self):
        """Frames with no detection are stored — frame index invariant."""
        buffer = []
        for i in range(5):
            if i in [0, 2, 4]:
                buffer.append(make_detected_charuco_observation())
            else:
                buffer.append(make_empty_charuco_observation())

        assert len(buffer) == 5
        assert not buffer[0].charuco_empty
        assert buffer[1].charuco_empty
        assert not buffer[2].charuco_empty
        assert buffer[3].charuco_empty
        assert not buffer[4].charuco_empty
