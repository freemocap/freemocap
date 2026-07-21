"""Unit and end-to-end tests for the robust charuco ground-plane estimator."""
import numpy as np
import pytest
from scipy.spatial.transform import Rotation
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition

from freemocap.core.tasks.calibration.shared.groundplane_math import (
    CharucoGeometryError,
    CharucoStabilityError,
    CharucoVisibilityError,
    aggregate_median_corners,
    estimate_board_groundplane,
    find_stable_window,
    fit_board_pose_kabsch,
    orient_up_toward_cameras,
)


def _known_pose() -> tuple[np.ndarray, np.ndarray]:
    rotation = Rotation.from_euler("xyz", [5.0, 7.0, 12.0], degrees=True).as_matrix()
    origin = np.array([120.0, -45.0, 8.0], dtype=np.float64)
    return rotation, origin


def test_fit_board_pose_kabsch_recovers_known_pose_exactly():
    board = CharucoBoardDefinition.create_test_data_7x5()
    board_points = board.corner_positions_board_frame
    rotation_true, origin_true = _known_pose()
    measured = (rotation_true @ board_points.T).T + origin_true

    rotation, origin = fit_board_pose_kabsch(board_points, measured)

    assert np.allclose(rotation, rotation_true, atol=1e-9)
    assert np.allclose(origin, origin_true, atol=1e-9)
    assert np.isclose(np.linalg.det(rotation), 1.0, atol=1e-9)
    assert np.allclose(rotation @ rotation.T, np.eye(3), atol=1e-9)


def test_fit_board_pose_kabsch_is_robust_to_noise():
    board = CharucoBoardDefinition.create_test_data_7x5()
    board_points = board.corner_positions_board_frame
    rotation_true, origin_true = _known_pose()
    rng = np.random.default_rng(0)
    measured = (rotation_true @ board_points.T).T + origin_true
    measured = measured + rng.normal(0.0, 1.0, measured.shape)

    rotation, origin = fit_board_pose_kabsch(board_points, measured)

    assert np.allclose(rotation, rotation_true, atol=0.02)
    assert np.allclose(origin, origin_true, atol=2.0)


def test_fit_board_pose_kabsch_raises_on_too_few_corners():
    pts = np.zeros((2, 3), dtype=np.float64)
    with pytest.raises(CharucoGeometryError):
        fit_board_pose_kabsch(pts, pts)


def test_fit_board_pose_kabsch_raises_on_collinear_corners():
    board_points = np.array(
        [[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0]], dtype=np.float64
    ) * 58.0
    measured = board_points + np.array([10.0, 20.0, 30.0])
    with pytest.raises(CharucoGeometryError):
        fit_board_pose_kabsch(board_points, measured)


def test_orient_up_keeps_z_when_already_toward_cameras():
    rotation = np.eye(3)
    origin = np.zeros(3)
    camera_centers = np.array([[0.0, 0.0, 2000.0], [500.0, 0.0, 1800.0]])

    out = orient_up_toward_cameras(rotation, origin, camera_centers)

    assert np.allclose(out, np.eye(3))


def test_orient_up_flips_z_when_pointing_away_from_cameras():
    rotation = np.eye(3)
    origin = np.zeros(3)
    camera_centers = np.array([[0.0, 0.0, -2000.0]])

    out = orient_up_toward_cameras(rotation, origin, camera_centers)

    assert np.allclose(out[:, 2], np.array([0.0, 0.0, -1.0]))
    assert np.allclose(out[:, 0], np.array([1.0, 0.0, 0.0]))
    assert np.isclose(np.linalg.det(out), 1.0, atol=1e-9)
    assert np.allclose(out @ out.T, np.eye(3), atol=1e-9)


def test_aggregate_median_corners_ignores_blinky_gaps():
    n_frames, n_corners = 20, 8
    rng = np.random.default_rng(1)
    true_pos = rng.normal(0.0, 100.0, (n_corners, 3))
    data = np.tile(true_pos[None, :, :], (n_frames, 1, 1)).astype(np.float64)
    data += rng.normal(0.0, 0.5, data.shape)
    data[::2, 3, :] = np.nan          # corner 3 blinks every other frame
    data[1:4, 5, :] = np.nan          # corner 5 missing for a few frames

    valid_ids, median_points = aggregate_median_corners(data, (0, n_frames))

    assert set(valid_ids.tolist()) == set(range(n_corners))
    assert np.allclose(median_points, true_pos, atol=0.5)


def test_aggregate_median_corners_excludes_undersampled_corner():
    n_frames, n_corners = 20, 8
    data = np.zeros((n_frames, n_corners, 3), dtype=np.float64)
    data[:] = np.arange(n_corners)[None, :, None]
    data[:, 7, :] = np.nan
    data[5:7, 7, :] = 7.0             # corner 7 seen in only 2 frames

    valid_ids, _ = aggregate_median_corners(
        data, (0, n_frames), min_observations_per_corner=3
    )

    assert valid_ids.tolist() == list(range(7))


def test_aggregate_median_corners_raises_when_nothing_observed():
    data = np.full((10, 8, 3), np.nan, dtype=np.float64)
    with pytest.raises(CharucoVisibilityError):
        aggregate_median_corners(data, (0, 10))


def test_find_stable_window_excludes_moving_segment():
    rng = np.random.default_rng(2)
    n_corners = 8
    base = rng.normal(0.0, 100.0, (n_corners, 3))
    still = np.tile(base[None, :, :], (30, 1, 1)).astype(np.float64)
    still += rng.normal(0.0, 0.05, still.shape)
    moving = np.tile(base[None, :, :], (10, 1, 1)).astype(np.float64)
    moving += np.arange(10)[:, None, None] * 5.0
    data = np.concatenate([moving, still], axis=0)  # 40 frames

    start, end = find_stable_window(data, velocity_threshold=2.0, min_run_frames=10)

    assert start == 10
    assert end == 40


def test_find_stable_window_raises_when_all_moving():
    n_corners = 8
    data = np.tile(np.zeros((1, n_corners, 3)), (20, 1, 1)).astype(np.float64)
    data += np.arange(20)[:, None, None] * 10.0
    with pytest.raises(CharucoStabilityError):
        find_stable_window(data, velocity_threshold=2.0, min_run_frames=10)


def test_find_stable_window_raises_when_run_too_short():
    rng = np.random.default_rng(3)
    n_corners = 8
    base = rng.normal(0.0, 100.0, (n_corners, 3))
    still = np.tile(base[None, :, :], (5, 1, 1)).astype(np.float64)
    still += rng.normal(0.0, 0.05, still.shape)
    moving = np.tile(base[None, :, :], (10, 1, 1)).astype(np.float64)
    moving += np.arange(10)[:, None, None] * 5.0
    data = np.concatenate([moving, still], axis=0)
    with pytest.raises(CharucoStabilityError):
        find_stable_window(data, velocity_threshold=2.0, min_run_frames=10)


def test_estimate_board_groundplane_end_to_end_recovers_pose():
    board = CharucoBoardDefinition.create_test_data_7x5()
    board_points = board.corner_positions_board_frame
    n_corners = board.n_corners

    rotation_true = Rotation.from_euler("xyz", [3.0, 4.0, 15.0], degrees=True).as_matrix()
    origin_true = np.array([200.0, 100.0, 5.0], dtype=np.float64)
    still_world = (rotation_true @ board_points.T).T + origin_true

    rng = np.random.default_rng(7)
    n_still = 40
    still = np.tile(still_world[None, :, :], (n_still, 1, 1)).astype(np.float64)
    still += rng.normal(0.0, 0.5, still.shape)            # triangulation noise
    dropout = rng.random((n_still, n_corners)) < 0.2      # 20% blinky dropout
    still[dropout] = np.nan

    moving = np.tile(still_world[None, :, :], (12, 1, 1)).astype(np.float64)
    moving += np.arange(12)[:, None, None] * 6.0          # board carried into place
    charuco_3d = np.concatenate([moving, still], axis=0)

    camera_centers = np.array(
        [
            [1500.0, 0.0, 1800.0],
            [-1500.0, 0.0, 1800.0],
            [0.0, 1500.0, 2000.0],
        ]
    )

    rotation, origin = estimate_board_groundplane(
        charuco_3d,
        board_points=board_points,
        camera_centers=camera_centers,
    )

    assert np.allclose(rotation, rotation_true, atol=0.03)
    assert np.allclose(origin, origin_true, atol=2.0)
    assert np.dot(rotation[:, 2], camera_centers.mean(axis=0) - origin) > 0
