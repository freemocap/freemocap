"""Unit tests for estimate_pose_points handling of empty/partial ChArUco rows.

Regression tests for the `len(corners) < 6` guard passing all-NaN rows:
skellytracker's anipose exporter turns an empty detection into a
(n_corners, 1, 2) all-NaN array whose ids list every corner id, so
len(corners) == n_corners and the row reached cv2.solvePnP with NaN image
points. OpenCV returns ret=True with NaN rvec/tvec for those, and the NaN
pose was stored as if it were valid.
"""

import cv2
import numpy as np
import pytest
from skellytracker.core.detectors.keypoint_detectors.charuco import (
    CharucoBoardDefinition,
)

from freemocap.core.tasks.calibration.charuco_board.charuco_board_ops import (
    estimate_pose_points,
    get_object_points,
)
from freemocap.core.tasks.calibration.shared.camera_extrinsics import CameraExtrinsics
from freemocap.core.tasks.calibration.shared.camera_intrinsics import CameraIntrinsics
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel


@pytest.fixture
def board() -> CharucoBoardDefinition:
    return CharucoBoardDefinition.create_test_data_7x5()


@pytest.fixture
def camera() -> CameraModel:
    return CameraModel(
        id="0",
        index=0,
        image_size=(1920, 1080),
        intrinsics=CameraIntrinsics.from_image_size(width=1920, height=1080),
        extrinsics=CameraExtrinsics(
            quaternion_wxyz=[1.0, 0.0, 0.0, 0.0],
            translation=[0.0, 0.0, 1500.0],
        ),
    )


def _projected_corners(
    board: CharucoBoardDefinition,
    camera: CameraModel,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Image points for the full board under a known pose, plus that pose."""
    rvec_true = np.array([[0.1], [0.05], [0.02]], dtype=np.float64)
    tvec_true = np.array([[0.0], [0.0], [1500.0]], dtype=np.float64)
    object_points = get_object_points(board)
    image_points, _ = cv2.projectPoints(
        object_points,
        rvec_true,
        tvec_true,
        camera.intrinsics.to_camera_matrix(),
        camera.intrinsics.to_dist_coeffs_5(),
    )
    return image_points.reshape(-1, 1, 2), rvec_true, tvec_true


def test_estimate_pose_points_returns_pose_for_valid_corners(
    board: CharucoBoardDefinition, camera: CameraModel
):
    corners, rvec_true, tvec_true = _projected_corners(board, camera)
    ids = np.arange(corners.shape[0])

    rvec, tvec = estimate_pose_points(board, camera, corners, ids)

    assert rvec is not None and tvec is not None
    assert np.isfinite(rvec).all() and np.isfinite(tvec).all()
    assert np.allclose(rvec, rvec_true, atol=1e-3)
    assert np.allclose(tvec, tvec_true, atol=1e-2)


def test_estimate_pose_points_returns_none_for_all_nan_row(
    board: CharucoBoardDefinition, camera: CameraModel
):
    """An empty detection (all-NaN corners, every corner id present) has no pose."""
    n_corners = (board.squares_x - 1) * (board.squares_y - 1)
    corners = np.full((n_corners, 1, 2), np.nan)
    ids = np.arange(n_corners)

    rvec, tvec = estimate_pose_points(board, camera, corners, ids)

    assert rvec is None and tvec is None


def test_estimate_pose_points_ignores_non_finite_corners(
    board: CharucoBoardDefinition, camera: CameraModel
):
    """Partially NaN rows solve from the finite corners only, never from NaNs."""
    corners, rvec_true, tvec_true = _projected_corners(board, camera)
    ids = np.arange(corners.shape[0])
    corners[3] = np.nan

    rvec, tvec = estimate_pose_points(board, camera, corners, ids)

    assert rvec is not None and tvec is not None
    assert np.isfinite(rvec).all() and np.isfinite(tvec).all()
    assert np.allclose(rvec, rvec_true, atol=1e-3)
    assert np.allclose(tvec, tvec_true, atol=1e-2)


def test_estimate_pose_points_returns_none_for_fewer_than_six_finite_corners(
    board: CharucoBoardDefinition, camera: CameraModel
):
    """Fewer than six finite corners cannot be solved, even if len(corners) >= 6."""
    corners, _, _ = _projected_corners(board, camera)
    ids = np.arange(corners.shape[0])
    corners[5:] = np.nan

    rvec, tvec = estimate_pose_points(board, camera, corners, ids)

    assert rvec is None and tvec is None
