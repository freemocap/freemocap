"""Fast, deterministic tests for posthoc reuse of realtime Charuco observations.

These exercise the read side (freemocap/core/pipeline/posthoc/video_node.py) with
hand-built cache pickles and timestamps CSVs — no cameras, no detection, no video —
so they run in milliseconds and pin the exact behaviour that shipped broken:

  * the cache was silently discarded — the reader asked the detector config for
    ``square_length_mm`` (which doesn't exist; the property is ``square_length``),
    hit AttributeError, and a bare ``except`` swallowed it, disabling the feature
    with only a DEBUG line; and
  * observations were keyed positionally, so realtime frames the pipeline dropped
    mis-aligned every later observation onto the wrong recorded video frame.

Both are regression-guarded below. All cache pickles read here are written by the
test itself into tmp_path — a trusted, self-produced fixture.
"""
import csv
import logging
import pickle
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.core import DetectionStageConfig, TrackerConfig
from skellytracker.core.data_primitives.observation import Observation
from skellytracker.core.detectors.keypoint_detectors.charuco import (
    CharucoBoardDefinition,
    CharucoDetectorConfig,
)
from skellytracker.core.detectors.keypoint_detectors.mediapipe.body.mediapipe_pose_detector import (
    MediapipePoseDetectorConfig,
)
from skellytracker.core.tracker.tracker import Tracker
from skellytracker.core.tracker.tracker_state import TrackerState

from freemocap.core.pipeline.posthoc.video_node import (
    CACHE_FILENAME,
    _build_recording_frame_cache,
    _get_observation,
    _load_cache_by_connection_frame,
    _load_recording_to_connection_frame_map,
)

BOARD = CharucoBoardDefinition(squares_x=5, squares_y=3, square_length_mm=54.0, aruco_dictionary_enum=2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _obs(connection_frame_number: int) -> Observation:
    return Observation(frame_number=connection_frame_number, image_size=(0, 0))


def _write_cache(recording_path: Path, observations: dict, board: CharucoBoardDefinition = BOARD) -> None:
    out = recording_path / "output_data"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / CACHE_FILENAME, "wb") as f:
        pickle.dump(
            {
                "board_definition": board,
                "observations": observations,
                "frame_range": (0, 0),
                "recording_uuid": "test",
            },
            f,
        )


def _write_camera_csv(recording_path: Path, camera_id: str, recording_to_connection: dict[int, int]) -> None:
    """Write a per-camera timestamps CSV in skellycam's path/format (only the two
    columns we read need real values)."""
    recording_info = RecordingInfo(
        recording_name=recording_path.name, recording_directory=str(recording_path.parent),
    )
    csv_path = Path(recording_info.camera_timestamps_file_path_from_camera_id(camera_id))
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["recording_frame_number", "connection_frame_number", "timestamp.utc.seconds"])
        for recording_frame, connection_frame in sorted(recording_to_connection.items()):
            writer.writerow([recording_frame, connection_frame, 0.0])


def _charuco_config(board: CharucoBoardDefinition = BOARD) -> TrackerConfig:
    return TrackerConfig(
        stages=[DetectionStageConfig(name="charuco", keypoint_detectors=[CharucoDetectorConfig(board=board)])]
    )


@pytest.fixture
def rec_path(tmp_path) -> Path:
    p = tmp_path / "2025-01-01_calibration"
    p.mkdir()
    return p


# ---------------------------------------------------------------------------
# Alignment + fallback
# ---------------------------------------------------------------------------

class TestPosthocCacheAlignment:
    def test_aligns_recording_frames_to_connection_keyed_observations(self, rec_path):
        # Realtime caught connection frames 100, 102, 105 (dropped 101, 103, 104).
        _write_cache(rec_path, {"cam0": {100: _obs(100), 102: _obs(102), 105: _obs(105)}})
        # Recorded video frames 0..5 came from connection frames 100..105.
        _write_camera_csv(rec_path, "cam0", {i: 100 + i for i in range(6)})

        cache = _build_recording_frame_cache(
            recording_path=rec_path, camera_id="cam0", detector_config=_charuco_config(),
        )
        # Only recorded frames whose connection number was captured are hits;
        # recorded frames 1, 3, 4 are misses (→ the node will detect them).
        assert set(cache.keys()) == {0, 2, 5}

    def test_get_observation_restamps_cached_obs_to_recording_frame(self, rec_path):
        _write_cache(rec_path, {"cam0": {100: _obs(100), 102: _obs(102)}})
        _write_camera_csv(rec_path, "cam0", {i: 100 + i for i in range(4)})
        cache = _build_recording_frame_cache(
            recording_path=rec_path, camera_id="cam0", detector_config=_charuco_config(),
        )
        # The cached obs carried its CONNECTION number (102). After lookup at
        # recorded frame 2 it must carry the RECORDING number so anipose rows align
        # with detected frames and across cameras.
        out, _ = _get_observation(
            frame_number=2,
            image=None,
            tracker=MagicMock(spec=Tracker),
            state=MagicMock(spec=TrackerState),
            cache=cache,
        )
        assert out.frame_number == 2

    def test_per_camera_drop_patterns_do_not_cross_contaminate(self, rec_path):
        # The cameras dropped DIFFERENT frames. Positional keying (the old bug) would
        # land cam0's and cam1's "3rd captured" observations on the same recorded
        # frame even though they came from different instants.
        _write_cache(rec_path, {
            "cam0": {100: _obs(100), 102: _obs(102), 104: _obs(104)},
            "cam1": {100: _obs(100), 101: _obs(101), 104: _obs(104)},
        })
        for cam in ("cam0", "cam1"):
            _write_camera_csv(rec_path, cam, {i: 100 + i for i in range(5)})

        cam0 = _build_recording_frame_cache(recording_path=rec_path, camera_id="cam0", detector_config=_charuco_config())
        cam1 = _build_recording_frame_cache(recording_path=rec_path, camera_id="cam1", detector_config=_charuco_config())
        assert set(cam0.keys()) == {0, 2, 4}
        assert set(cam1.keys()) == {0, 1, 4}

    def test_missing_csv_forces_full_detection(self, rec_path, caplog):
        # Valid cache, but no timestamps CSV to align it → must detect everything
        # rather than guess an alignment.
        _write_cache(rec_path, {"cam0": {100: _obs(100)}})
        with caplog.at_level(logging.WARNING):
            cache = _build_recording_frame_cache(
                recording_path=rec_path, camera_id="cam0", detector_config=_charuco_config(),
            )
        assert cache is None
        assert any("timestamps csv" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# Validation: applies-or-not, and fail LOUDLY (regressions for the silent miss)
# ---------------------------------------------------------------------------

class TestPosthocCacheValidation:
    def test_matching_board_and_cache_actually_loads(self, rec_path):
        # Regression for the shipped silent-miss bug: a perfectly matching board +
        # cache must load. (It didn't, because the reader asked the config for the
        # non-existent ``square_length_mm`` and swallowed the AttributeError.)
        _write_cache(rec_path, {"cam0": {0: _obs(0), 1: _obs(1)}})
        loaded = _load_cache_by_connection_frame(
            recording_path=rec_path, camera_id="cam0", detector_config=_charuco_config(),
        )
        assert loaded is not None
        assert set(loaded.keys()) == {0, 1}

    def test_board_mismatch_rejected_visibly(self, rec_path, caplog):
        _write_cache(rec_path, {"cam0": {0: _obs(0)}}, board=BOARD)  # 5x3, 54mm
        wrong = _charuco_config(
            board=CharucoBoardDefinition(squares_x=7, squares_y=5, square_length_mm=58.0),
        )
        with caplog.at_level(logging.INFO):
            loaded = _load_cache_by_connection_frame(
                recording_path=rec_path, camera_id="cam0", detector_config=wrong,
            )
        assert loaded is None
        assert any("board mismatch" in r.message.lower() for r in caplog.records), \
            "a board mismatch must be logged visibly, not silently swallowed"

    def test_malformed_cache_rejected_loudly(self, rec_path, caplog):
        # Stale positional format: observations as a list, not a connection-keyed dict.
        _write_cache(rec_path, {"cam0": [_obs(0), _obs(1)]})
        with caplog.at_level(logging.WARNING):
            loaded = _load_cache_by_connection_frame(
                recording_path=rec_path, camera_id="cam0", detector_config=_charuco_config(),
            )
        assert loaded is None
        assert any(r.levelno >= logging.WARNING for r in caplog.records), \
            "a malformed cache must produce a visible WARNING, not a silent DEBUG no-op"

    def test_non_charuco_detector_returns_none(self, rec_path):
        _write_cache(rec_path, {"cam0": {0: _obs(0)}})

        mediapipe_config = TrackerConfig(
            stages=[DetectionStageConfig(name="body", keypoint_detectors=[MediapipePoseDetectorConfig()])]
        )
        loaded = _load_cache_by_connection_frame(
            recording_path=rec_path, camera_id="cam0", detector_config=mediapipe_config,
        )
        assert loaded is None

    def test_camera_absent_from_cache_returns_none(self, rec_path):
        _write_cache(rec_path, {"cam0": {0: _obs(0)}})
        loaded = _load_cache_by_connection_frame(
            recording_path=rec_path, camera_id="cam_other", detector_config=_charuco_config(),
        )
        assert loaded is None


# ---------------------------------------------------------------------------
# CSV mapping
# ---------------------------------------------------------------------------

class TestTimestampsCsvMapping:
    def test_parses_recording_to_connection_pairs(self, rec_path):
        _write_camera_csv(rec_path, "cam0", {0: 50, 1: 51, 2: 53})
        mapping = _load_recording_to_connection_frame_map(recording_path=rec_path, camera_id="cam0")
        assert mapping == {0: 50, 1: 51, 2: 53}

    def test_missing_csv_returns_none(self, rec_path):
        assert _load_recording_to_connection_frame_map(recording_path=rec_path, camera_id="nope") is None
