"""A calibration that does not fit the live cameras is reported ONCE, not per frame.

These are the regression tests for the log storm: `_calibrated_cameras()` logged at
ERROR on every emitted frame, and `try_angulate()` counted every camera-identity
mismatch as a triangulation failure until it destroyed the calibration.
"""

import logging

import numpy as np
import pytest

from freemocap.core.tasks.calibration.shared.calibration_camera_binding import CalibrationMatchKind
from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from freemocap.core.tasks.calibration.shared.calibration_state import CalibrationStateTracker
from freemocap.core.tasks.calibration.shared.camera_extrinsics import CameraExtrinsics
from freemocap.core.tasks.calibration.shared.camera_intrinsics import CameraIntrinsics
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel
from freemocap.core.tasks.triangulation.triangulator import Triangulator
from skellytracker.core.data_primitives.observation import Observation
from skellytracker.core.detectors.keypoint_detectors.charuco.charuco_board_definition import (
    CharucoBoardDefinition,
)

FITTING_CAMERAS = {"cam0": 0, "cam1": 1, "cam2": 2}
NON_FITTING_CAMERAS = {"d441": 0, "2ea4": 1, "be07": 2, "583d": 3}


def build_calibration_camera(camera_id: str, index: int) -> CameraModel:
    return CameraModel(
        id=camera_id,
        index=index,
        image_size=(1280, 720),
        intrinsics=CameraIntrinsics(fx=900.0, fy=900.0, cx=640.0, cy=360.0),
        extrinsics=CameraExtrinsics(
            quaternion_wxyz=np.array([1.0, 0.0, 0.0, 0.0]),
            translation=np.array([float(index) * 100.0, 0.0, 0.0]),
        ),
    )


def build_loaded_tracker(camera_ids: tuple[str, ...] = ("cam0", "cam1", "cam2")) -> CalibrationStateTracker:
    """A tracker holding a calibration, without touching the filesystem."""
    cameras = [build_calibration_camera(cid, i) for i, cid in enumerate(camera_ids)]
    tracker = CalibrationStateTracker()
    tracker._calibration = CalibrationResult(
        cameras=cameras,
        board=CharucoBoardDefinition(squares_x=5, squares_y=3, square_length_mm=50.0),
        reprojection_error_px=0.5,
        initial_cost=1.0,
        final_cost=0.1,
        n_iterations=10,
        time_seconds=1.0,
        n_observations_used=100,
        n_observations_rejected=0,
    )
    tracker._triangulator = Triangulator(cameras=cameras)
    tracker._is_valid = True
    tracker._calibration_generation = 1
    return tracker


def build_empty_observation(frame_number: int = 0) -> Observation:
    """Shape-valid but pointless — the applicability gate returns before it is read."""
    return Observation(frame_number=frame_number, image_size=(720, 1280))


def warnings_and_errors(caplog: pytest.LogCaptureFixture) -> tuple[list, list]:
    return (
        [r for r in caplog.records if r.levelno == logging.WARNING],
        [r for r in caplog.records if r.levelno >= logging.ERROR],
    )


def test_non_fitting_calibration_warns_exactly_once_over_many_binds(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The spam test. 100 binds of the same non-fitting camera set -> one warning."""
    tracker = build_loaded_tracker()

    with caplog.at_level(logging.DEBUG):
        for _ in range(100):
            binding = tracker.bind_live_cameras(live_camera_indices=NON_FITTING_CAMERAS)

    assert binding is not None
    assert binding.kind is CalibrationMatchKind.UNMATCHED
    assert tracker.is_applicable() is False

    warnings, errors = warnings_and_errors(caplog)
    assert len(warnings) == 1, [r.getMessage() for r in warnings]
    assert errors == []


def test_camera_set_change_produces_exactly_one_more_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    tracker = build_loaded_tracker()

    with caplog.at_level(logging.DEBUG):
        for _ in range(20):
            tracker.bind_live_cameras(live_camera_indices=NON_FITTING_CAMERAS)
        for _ in range(20):
            tracker.bind_live_cameras(live_camera_indices={"aaaa": 0, "bbbb": 7})

    warnings, errors = warnings_and_errors(caplog)
    assert len(warnings) == 2, [r.getMessage() for r in warnings]
    assert errors == []


def test_reloading_a_calibration_re_evaluates_even_with_the_same_camera_set(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The binding key is keyed on a generation counter, not the file mtime."""
    tracker = build_loaded_tracker()

    with caplog.at_level(logging.DEBUG):
        for _ in range(10):
            tracker.bind_live_cameras(live_camera_indices=NON_FITTING_CAMERAS)
        tracker._calibration_generation += 1  # as a successful reload would
        for _ in range(10):
            tracker.bind_live_cameras(live_camera_indices=NON_FITTING_CAMERAS)

    warnings, _ = warnings_and_errors(caplog)
    assert len(warnings) == 2


def test_fitting_calibration_is_applicable_and_does_not_warn(
    caplog: pytest.LogCaptureFixture,
) -> None:
    tracker = build_loaded_tracker()

    with caplog.at_level(logging.DEBUG):
        binding = tracker.bind_live_cameras(live_camera_indices=FITTING_CAMERAS)

    assert binding is not None
    assert binding.kind is CalibrationMatchKind.EXACT
    assert tracker.is_applicable() is True

    warnings, errors = warnings_and_errors(caplog)
    assert warnings == []
    assert errors == []


def test_identity_mismatch_never_touches_the_failure_counter(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A calibration that does not fit is not a triangulation failure.

    Previously this path raised CameraIdMismatchError inside try_angulate's bare
    `except Exception`, so 10 frames (well under a second) destroyed the calibration.
    """
    tracker = build_loaded_tracker()
    tracker.bind_live_cameras(live_camera_indices=NON_FITTING_CAMERAS)
    caplog.clear()

    with caplog.at_level(logging.DEBUG):
        for frame_number in range(50):
            result = tracker.try_angulate(
                frame_number=frame_number,
                frame_observations_by_camera={
                    "d441": build_empty_observation(frame_number),
                    "2ea4": build_empty_observation(frame_number),
                },
                max_reprojection_error_px=10.0,
            )
            assert result is None

    assert tracker._consecutive_failure_count == 0
    _, errors = warnings_and_errors(caplog)
    assert errors == []


def test_not_applicable_is_non_destructive() -> None:
    """The calibration is fine; it just does not fit these cameras.

    Discarding it here (as `_invalidate()` would) also preserves the file mtime, which
    would permanently block the reload that fixes the problem.
    """
    tracker = build_loaded_tracker()

    for _ in range(30):
        tracker.try_angulate(
            frame_number=0,
            frame_observations_by_camera={"d441": build_empty_observation()},
            max_reprojection_error_px=10.0,
        )
        tracker.bind_live_cameras(live_camera_indices=NON_FITTING_CAMERAS)

    assert tracker.is_applicable() is False
    assert tracker.is_valid is True
    assert tracker.calibration is not None
    assert tracker._triangulator is not None


def test_recovery_when_the_camera_set_starts_fitting_again(
    caplog: pytest.LogCaptureFixture,
) -> None:
    tracker = build_loaded_tracker()
    tracker.bind_live_cameras(live_camera_indices=NON_FITTING_CAMERAS)
    assert tracker.is_applicable() is False

    with caplog.at_level(logging.DEBUG):
        tracker.bind_live_cameras(live_camera_indices=FITTING_CAMERAS)

    assert tracker.is_applicable() is True
    _, errors = warnings_and_errors(caplog)
    assert errors == []
