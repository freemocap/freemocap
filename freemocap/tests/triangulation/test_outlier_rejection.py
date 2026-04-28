"""Unit tests for the unified triangulation module.

Covers:
  - triangulate_with_outlier_rejection clean-data parity with triangulate_simple
  - triangulate_with_outlier_rejection actually rejects a corrupt camera
  - Triangulator.triangulate dispatches across dict / 3D-array / 4D-array inputs
"""
import numpy as np

from freemocap.core.tasks.calibration.shared.calibration_models import (
    CameraExtrinsics,
    CameraIntrinsics,
    CameraModel,
)
from freemocap.core.tasks.triangulation.helpers.outlier_rejection import (
    triangulate_with_outlier_rejection,
)
from freemocap.core.tasks.triangulation import triangulate_simple, project_point_to_camera
from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig
from freemocap.core.tasks.triangulation.triangulator import Triangulator


# =============================================================================
# Synthetic 4-camera scene
# =============================================================================


def _make_synthetic_extrinsics() -> tuple[np.ndarray, list[CameraModel]]:
    """4 cameras around a 1m scene cube, looking inward at the origin.

    Returns (extrinsics_mats (4,3,4), CameraModels with identity-like intrinsics).
    """
    rng = np.random.default_rng(42)
    rotations = []
    translations = []
    extrinsics_mats = np.zeros((4, 3, 4), dtype=np.float64)

    # Place cameras at the corners of a square in the XY plane, looking at origin.
    cam_positions = np.array(
        [
            [2.0, 0.0, 0.5],
            [0.0, 2.0, 0.5],
            [-2.0, 0.0, 0.5],
            [0.0, -2.0, 0.5],
        ]
    )

    cameras: list[CameraModel] = []
    for i, pos in enumerate(cam_positions):
        # Rotation that points the camera at the origin
        forward = -pos / np.linalg.norm(pos)
        up = np.array([0.0, 0.0, 1.0])
        right = np.cross(forward, up)
        right = right / np.linalg.norm(right)
        up = np.cross(right, forward)
        # Camera coordinate frame: right (x), -up (y, image y flips), forward (z)
        R = np.stack([right, -up, forward], axis=0)
        t = -R @ pos
        extrinsics_mats[i, :, :3] = R
        extrinsics_mats[i, :, 3] = t
        rotations.append(R)
        translations.append(t)

        cameras.append(
            CameraModel(
                id=f"cam_{i}",
                image_size=(640, 480),
                intrinsics=CameraIntrinsics(fx=500.0, fy=500.0, cx=320.0, cy=240.0),
                extrinsics=CameraExtrinsics.from_rodrigues(
                    rvec=np.asarray(__import__("cv2").Rodrigues(R)[0]).ravel(),
                    tvec=t,
                ),
            )
        )
    return extrinsics_mats, cameras


def _project_normalized(point_3d: np.ndarray, extrinsics_mats: np.ndarray) -> np.ndarray:
    """Project a single 3D point through each camera's [R|t] -> normalized 2D."""
    return np.array(
        [project_point_to_camera(point_3d=point_3d, extrinsics_mat=mat) for mat in extrinsics_mats]
    )


# =============================================================================
# Tests
# =============================================================================


def test_outlier_rejection_clean_data_matches_simple_dlt():
    """With perfectly clean observations the outlier-rejection method should match simple DLT
    and return uniform per-camera weights (all 1.0 - the early-exit branch)."""
    extrinsics_mats, _ = _make_synthetic_extrinsics()
    truth = np.array([0.1, 0.2, 0.3])
    obs = _project_normalized(point_3d=truth, extrinsics_mats=extrinsics_mats)

    p3d_simple = triangulate_simple(points=obs, extrinsics_mats=extrinsics_mats)
    p3d_robust, weights = triangulate_with_outlier_rejection(
        points_2d=obs,
        extrinsics_mats=extrinsics_mats,
        target_reprojection_error=1e-3,
    )

    np.testing.assert_allclose(p3d_simple, truth, atol=1e-9)
    np.testing.assert_allclose(p3d_robust, truth, atol=1e-9)
    np.testing.assert_allclose(p3d_robust, p3d_simple, atol=1e-9)
    # Early-exit branch returns uniform 1.0 weights.
    np.testing.assert_allclose(weights, 1.0)


def test_outlier_rejection_recovers_from_corrupt_camera():
    """If one camera's observation is corrupted, the recovered 3D point should be closer to
    ground truth than plain DLT, and the corrupt camera's weight should be lowest."""
    extrinsics_mats, _ = _make_synthetic_extrinsics()
    truth = np.array([0.1, 0.2, 0.3])
    obs = _project_normalized(point_3d=truth, extrinsics_mats=extrinsics_mats)

    corrupt_idx = 2
    obs_corrupt = obs.copy()
    obs_corrupt[corrupt_idx] += np.array([0.5, 0.5])  # large normalized-coord offset

    p3d_simple = triangulate_simple(points=obs_corrupt, extrinsics_mats=extrinsics_mats)
    p3d_robust, weights = triangulate_with_outlier_rejection(
        points_2d=obs_corrupt,
        extrinsics_mats=extrinsics_mats,
        target_reprojection_error=0.001,
        maximum_cameras_to_drop=1,
    )

    err_simple = float(np.linalg.norm(p3d_simple - truth))
    err_robust = float(np.linalg.norm(p3d_robust - truth))
    assert err_robust < err_simple, (
        f"Outlier rejection should beat plain DLT on corrupt input; "
        f"err_simple={err_simple}, err_robust={err_robust}"
    )

    # The corrupt camera should carry the lowest weight.
    other_weights = np.delete(weights, corrupt_idx)
    assert weights[corrupt_idx] < float(np.min(other_weights)), (
        f"Corrupt camera weight ({weights[corrupt_idx]}) should be < min of others "
        f"({float(np.min(other_weights))}); got weights={weights}"
    )


def test_triangulator_dispatch_across_input_shapes():
    """All three input shapes (dict, 3D, 4D) should produce the same 3D points;
    use_outlier_rejection True/False should match within 1e-9 on clean data."""
    _, cameras = _make_synthetic_extrinsics()
    triangulator = Triangulator(cameras=cameras)

    truth = np.array([10.0, 20.0, 30.0])  # in mm-ish scale, doesn't matter

    # Project through each camera's full intrinsics+extrinsics into pixel coords.
    pixel_obs = triangulator.project(points_3d=truth.reshape(1, 3))  # (n_cameras, 1, 2)

    # Build the three input shapes:
    arr_3d = pixel_obs.reshape(triangulator.n_cameras, 1, 2)             # (n_cameras, n_points=1, 2)
    arr_4d = pixel_obs.reshape(triangulator.n_cameras, 1, 1, 2)          # (n_cameras, n_frames=1, n_points=1, 2)
    dict_input = {
        cam.name: pixel_obs[i].reshape(1, 1, 2)  # (n_frames, n_points, 2)
        for i, cam in enumerate(triangulator.cameras)
    }

    cfg_off = TriangulationConfig(use_outlier_rejection=False)
    cfg_on = TriangulationConfig(use_outlier_rejection=True, target_reprojection_error=1e-3)

    res_3d = triangulator.triangulate(data2d=arr_3d, config=cfg_off)
    res_4d = triangulator.triangulate(data2d=arr_4d, config=cfg_off)
    res_dict = triangulator.triangulate(data2d=dict_input, config=cfg_off)
    res_or = triangulator.triangulate(data2d=arr_3d, config=cfg_on)

    assert res_3d.points_3d.shape == (1, 3)
    assert res_4d.points_3d.shape == (1, 1, 3)
    assert res_dict.points_3d.shape == (1, 1, 3)
    assert res_or.points_3d.shape == (1, 3)

    np.testing.assert_allclose(res_3d.points_3d.ravel(), truth, atol=1e-6)
    np.testing.assert_allclose(res_4d.points_3d.ravel(), truth, atol=1e-6)
    np.testing.assert_allclose(res_dict.points_3d.ravel(), truth, atol=1e-6)
    np.testing.assert_allclose(res_or.points_3d.ravel(), res_3d.points_3d.ravel(), atol=1e-9)
