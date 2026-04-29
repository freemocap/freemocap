"""Bundle-adjustment solver operating directly on list[CameraModel].

Free-function port of what was AniposeCameraGroup. The optimizer mutates
the supplied cameras list in place: each iteration replaces extrinsics
and overwrites intrinsics fields per `camera_model_solver_ops`.
"""
from __future__ import annotations

import logging
import multiprocessing.synchronize
from typing import Any

import cv2
import numpy as np
from freemocap.core.tasks.calibration.shared.transform_math import build_transformation_matrix, get_rtvec
from numba import jit
from numpy.typing import NDArray
from scipy import optimize
from scipy.sparse import dok_matrix
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.tasks.calibration.charuco import charuco_board_ops
from freemocap.core.tasks.calibration.anipose_calibration.helpers.camera_model_solver_ops import (
    PARAMS_PER_CAMERA,
    apply_camera_params,
    apply_extrinsics,
    pack_camera_params,
)
from freemocap.core.tasks.calibration.anipose_calibration.helpers.freemocap_anipose import (
    extract_points,
    extract_roration_translation_vectors,
    get_connections,
    get_error_dict,
    get_initial_extrinsics,
    merge_rows,
    remap_ids,
    resample_points,
    subset_extra,
    transform_points, BoardObservations,
)
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel
from freemocap.core.tasks.calibration.charuco.charuco_board import CharucoBoardDefinition

logger = logging.getLogger(__name__)


def camera_ids_from_camera_models(cameras: list[CameraModel]) -> list[CameraIdString]:
    return [CameraIdString(cam.id) for cam in cameras]


# =============================================================================
# TRIANGULATION / REPROJECTION (delegate to shared Triangulator)
# =============================================================================


def _make_triangulator(cameras: list[CameraModel]):
    """Build a Triangulator from the current (in-flight) camera state.

    Solver iterations mutate camera intrinsics/extrinsics, so this rebuilds
    on every call. Construction cost is microseconds; solver iterations
    take seconds.
    """
    from freemocap.core.tasks.triangulation.triangulator import Triangulator
    return Triangulator(cameras=cameras)


def triangulate(
        cameras: list[CameraModel],
        points: NDArray[np.float64],
        undistort: bool = True,
        use_outlier_rejection: bool = True,
        kill_event: multiprocessing.synchronize.Event | None = None,
) -> NDArray[np.float64] | None:
    """Triangulate a (num_cameras, N, 2) image-point array to (N, 3) world points."""
    from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig

    if points.shape[0] != len(cameras):
        raise ValueError(
            f"First dim should equal number of cameras ({len(cameras)}), "
            f"but shape is {points.shape}"
        )

    one_point = False
    if len(points.shape) == 2:
        points = points.reshape(-1, 1, 2)
        one_point = True

    if kill_event is not None and kill_event.is_set():
        return None

    triangulator = _make_triangulator(cameras)
    result = triangulator.triangulate(
        data2d=points,
        config=TriangulationConfig(use_outlier_rejection=use_outlier_rejection),
        assume_undistorted_normalized=not undistort,
    )
    out = result.points_3d
    if one_point:
        out = out[0]
    return out


def reprojection_error(
        cameras: list[CameraModel],
        points_3d: NDArray[np.float64],
        points_2d: NDArray[np.float64],
        mean: bool = False,
) -> NDArray[np.float64] | float:
    """Reprojection error between 3-D points and 2-D observations."""
    one_point = False
    if len(points_3d.shape) == 1 and len(points_2d.shape) == 2:
        points_3d = points_3d.reshape(1, 3)
        points_2d = points_2d.reshape(-1, 1, 2)
        one_point = True

    num_cameras, num_points, _ = points_2d.shape
    if points_3d.shape != (num_points, 3):
        raise ValueError(
            f"2D/3D shape mismatch: 2D={points_2d.shape}, 3D={points_3d.shape}"
        )

    triangulator = _make_triangulator(cameras)
    if mean:
        errors = triangulator.mean_reprojection_error(
            points_3d=points_3d, points_2d_pixel=points_2d,
        )
    else:
        errors = triangulator.signed_reprojection_error(
            points_3d=points_3d, points_2d_pixel=points_2d,
        )

    if one_point:
        errors = float(errors[0]) if mean else errors.reshape(-1, 2)
    return errors


def average_error(
        cameras: list[CameraModel],
        points_2d: NDArray[np.float64],
        median: bool = False,
) -> float:
    points_3d = triangulate(cameras, points_2d)
    errors = reprojection_error(cameras, points_3d, points_2d, mean=True)
    return float(np.median(errors)) if median else float(np.mean(errors))


# =============================================================================
# BUNDLE ADJUSTMENT
# =============================================================================


def iterative_bundle_adjustment(
        cameras: list[CameraModel],
        points_2d: NDArray[np.float64],
        board_observations: BoardObservations,
        num_iterations: int = 10,
        damping_start: float = 15,
        damping_end: float = 1,
        max_nfev: int = 200,
        ftol: float = 1e-4,
        num_samples_per_iteration: int = 100,
        num_samples_full: int = 1000,
        error_threshold: float = 0.3,
) -> float:
    """Iterative bundle adjustment with a decaying outlier-rejection schedule.

    Mutates `cameras` in place. Returns the final median reprojection error.
    """
    if points_2d.shape[0] != len(cameras):
        raise ValueError(
            f"First dim should equal number of cameras ({len(cameras)}), "
            f"but shape is {points_2d.shape}"
        )

    points_2d_full = points_2d
    board_observations_full = board_observations

    points_2d, board_observations = resample_points(
        points_2d_full, board_observations_full, num_samples=num_samples_full
    )
    error = average_error(cameras, points_2d, median=True)

    logger.info(f"Reprojection error before bundle adjustment: {error:.4f} pixels ")

    mus = np.exp(np.linspace(np.log(damping_start), np.log(damping_end), num=num_iterations))

    for iteration in range(num_iterations):
        points_2d, board_observations = resample_points(
            points_2d_full, board_observations_full, num_samples=num_samples_full
        )
        points_3d = triangulate(cameras, points_2d)
        errors_full = reprojection_error(cameras, points_3d, points_2d, mean=False)
        errors_norm = reprojection_error(cameras, points_3d, points_2d, mean=True)

        error_dict = get_error_dict(errors_full)
        max_error = 0
        min_error = 0
        for k, v in error_dict.items():
            num, percents = v
            max_error = max(percents[-1], max_error)
            min_error = max(percents[0], min_error)
        mu = max(min(max_error, mus[iteration]), min_error)

        good = errors_norm < mu
        board_observations_good = subset_extra(board_observations, good)
        points_2d_samp, board_observations_samp = resample_points(
            points_2d[:, good], board_observations_good, num_samples=num_samples_per_iteration
        )

        error = float(np.median(errors_norm))

        if error < error_threshold:
            break

        logger.info(
            f"Iteration {iteration + 1}/{num_iterations}: error={error:.4f}, mu={mu:.2f}, inliers={np.sum(good)}/{len(good)}")

        bundle_adjust(
            cameras,
            points_2d_samp,
            board_observations_samp,
            loss="linear",
            ftol=ftol,
            max_nfev=max_nfev,
        )

    points_2d, board_observations = resample_points(
        points_2d_full, board_observations_full, num_samples=num_samples_full
    )
    points_3d = triangulate(cameras, points_2d)
    errors_full = reprojection_error(cameras, points_3d, points_2d, mean=False)
    errors_norm = reprojection_error(cameras, points_3d, points_2d, mean=True)
    error_dict = get_error_dict(errors_full)

    max_error = 0
    min_error = 0
    for k, v in error_dict.items():
        num, percents = v
        max_error = max(percents[-1], max_error)
        min_error = max(percents[0], min_error)
    mu = max(max(max_error, damping_end), min_error)

    good = errors_norm < mu
    board_observations_good = subset_extra(board_observations, good)
    bundle_adjust(
        cameras,
        points_2d[:, good],
        board_observations_good,
        loss="linear",
        ftol=ftol,
        max_nfev=max(200, max_nfev),
    )

    return average_error(cameras, points_2d, median=True)


def bundle_adjust(
        cameras: list[CameraModel],
        points_2d: NDArray[np.float64],
        board_observations: BoardObservations,
        loss: str = "linear",
        threshold: float = 50,
        ftol: float = 1e-4,
        max_nfev: int = 1000,
        start_params: NDArray[np.float64] | None = None,
) -> float:
    """Single scipy.least_squares bundle-adjust pass; mutates cameras in place."""
    if points_2d.shape[0] != len(cameras):
        raise ValueError(
            f"First dim should equal number of cameras ({len(cameras)}), "
            f"but shape is {points_2d.shape}"
        )

    board_observations["ids_map"] = remap_ids(board_observations["ids"])

    x0, num_camera_params = _initialize_params_bundle(cameras, points_2d, board_observations)

    if start_params is not None:
        x0 = start_params
        num_camera_params = PARAMS_PER_CAMERA

    jac_sparse = _jac_sparsity_bundle(cameras, points_2d, num_camera_params, board_observations)

    opt = optimize.least_squares(
        _error_fun_bundle,
        x0,
        jac_sparsity=jac_sparse,
        f_scale=threshold,
        x_scale="jac",
        loss=loss,
        ftol=ftol,
        method="trf",
        tr_solver="lsmr",
        verbose=2,
        max_nfev=max_nfev,
        args=(cameras, points_2d, num_camera_params, board_observations),
    )

    for camera_index, cam in enumerate(cameras):
        param_start = camera_index * num_camera_params
        param_end = (camera_index + 1) * num_camera_params
        apply_camera_params(cam, opt.x[param_start:param_end])

    return average_error(cameras, points_2d)


@jit(parallel=True, forceobj=True)
def _error_fun_bundle(
        params: NDArray[np.float64],
        cameras: list[CameraModel],
        points_2d: NDArray[np.float64],
        num_camera_params: int,
        board_observations: BoardObservations,
) -> NDArray[np.float64]:
    good = ~np.isnan(points_2d)
    num_cameras = len(cameras)

    for camera_index in range(num_cameras):
        param_start = camera_index * num_camera_params
        param_end = (camera_index + 1) * num_camera_params
        apply_camera_params(cameras[camera_index], params[param_start:param_end])

    total_cam_params = num_camera_params * num_cameras
    num_3d_params = points_2d.shape[1] * 3
    points_3d_test = params[total_cam_params: total_cam_params + num_3d_params].reshape(-1, 3)
    errors_reproj = reprojection_error(cameras, points_3d_test, points_2d)[good]

    ids = board_observations["ids_map"]
    objp = board_observations["objp"]
    min_scale = np.min(objp[objp > 0])
    num_boards = int(np.max(ids)) + 1
    board_param_start = total_cam_params + num_3d_params
    rvecs = params[board_param_start: board_param_start + num_boards * 3].reshape(-1, 3)
    tvecs = params[board_param_start + num_boards * 3: board_param_start + num_boards * 6].reshape(-1, 3)
    expected = transform_points(objp, rvecs[ids], tvecs[ids])
    errors_obj = 2 * (points_3d_test - expected).ravel() / min_scale

    return np.hstack([errors_reproj, errors_obj])


def _jac_sparsity_bundle(
        cameras: list[CameraModel],
        points_2d: NDArray[np.float64],
        num_camera_params: int,
        board_observations: BoardObservations,
) -> dok_matrix:
    point_indices = np.zeros(points_2d.shape, dtype="int32")
    cam_indices = np.zeros(points_2d.shape, dtype="int32")

    for point_index in range(points_2d.shape[1]):
        point_indices[:, point_index] = point_index
    for camera_index in range(points_2d.shape[0]):
        cam_indices[camera_index] = camera_index

    good = ~np.isnan(points_2d)

    ids = board_observations["ids_map"]
    num_boards = int(np.max(ids)) + 1
    total_board_params = num_boards * 6

    num_cameras = points_2d.shape[0]
    num_points = points_2d.shape[1]
    total_params_reproj = num_cameras * num_camera_params + num_points * 3
    num_params = total_params_reproj + total_board_params

    num_good_values = np.sum(good)
    num_errors = num_good_values + (num_points * 3 if board_observations is not None else 0)

    A_sparse = dok_matrix((num_errors, num_params), dtype="int16")

    cam_indices_good = cam_indices[good]
    point_indices_good = point_indices[good]
    ix = np.arange(num_good_values)

    for param_offset in range(num_camera_params):
        A_sparse[ix, cam_indices_good * num_camera_params + param_offset] = 1
    for coord in range(3):
        A_sparse[ix, num_cameras * num_camera_params + point_indices_good * 3 + coord] = 1

    if board_observations is not None:
        point_ix = np.arange(num_points)
        for i in range(3):
            for j in range(3):
                A_sparse[num_good_values + point_ix * 3 + i, total_params_reproj + ids * 3 + j] = 1
                A_sparse[
                    num_good_values + point_ix * 3 + i,
                    total_params_reproj + num_boards * 3 + ids * 3 + j,
                ] = 1
        for i in range(3):
            A_sparse[
                num_good_values + point_ix * 3 + i,
                num_cameras * num_camera_params + point_ix * 3 + i,
            ] = 1

    return A_sparse


def _initialize_params_bundle(
        cameras: list[CameraModel],
        points_2d: NDArray[np.float64],
        board_observations: BoardObservations,
) -> tuple[NDArray[np.float64], int]:
    """Build the initial parameter vector for bundle adjustment.

    Layout: [camera_params... | 3d_points... | board_rvecs... | board_tvecs...]
    """

    cam_params = np.hstack([pack_camera_params(cam) for cam in cameras])
    num_camera_params = len(cam_params) // len(cameras)
    total_cam_params = len(cam_params)

    num_cameras, num_points, _ = points_2d.shape
    if num_cameras != len(cameras):
        raise ValueError("Camera count mismatch between cameras and 2D points")

    points_3d = triangulate(cameras, points_2d)

    ids = board_observations["ids_map"]
    num_boards = int(np.max(ids[~np.isnan(ids)])) + 1
    total_board_params = num_boards * 6

    rvecs = np.zeros((num_boards, 3), dtype="float64")
    tvecs = np.zeros((num_boards, 3), dtype="float64")

    if "rvecs" in board_observations and "tvecs" in board_observations:
        rvecs_all = board_observations["rvecs"]
        tvecs_all = board_observations["tvecs"]
        for board_num in range(num_boards):
            point_id = np.where(ids == board_num)[0][0]
            cam_ids_possible = np.where(~np.isnan(points_2d[:, point_id, 0]))[0]
            cam_id = np.random.choice(cam_ids_possible)
            M_cam = build_transformation_matrix(
                cameras[cam_id].extrinsics.rodrigues_vector,
                cameras[cam_id].extrinsics.translation,
            )
            M_board_cam = build_transformation_matrix(rvecs_all[cam_id, point_id], tvecs_all[cam_id, point_id])
            M_board = np.linalg.inv(M_cam) @ M_board_cam
            rvec, tvec = get_rtvec(M_board)
            rvecs[board_num] = rvec
            tvecs[board_num] = tvec

    x0 = np.zeros(total_cam_params + points_3d.size + total_board_params)
    x0[:total_cam_params] = cam_params
    x0[total_cam_params: total_cam_params + points_3d.size] = points_3d.ravel()

    if board_observations is not None:
        board_start = total_cam_params + points_3d.size
        x0[board_start: board_start + num_boards * 3] = rvecs.ravel()
        x0[board_start + num_boards * 3: board_start + num_boards * 6] = tvecs.ravel()

    return x0, num_camera_params


# =============================================================================
# CALIBRATION ENTRY POINT (replaces AniposeCameraGroup.calibrate_rows)
# =============================================================================


def calibrate_cameras_from_rows(
        cameras: list[CameraModel],
        all_rows: list[list[dict[str, Any]]],
        board: CharucoBoardDefinition,
) -> tuple[float, list, list]:
    """Calibrate cameras from charuco board observation rows.

    Mutates `cameras` in place. Returns (reprojection_error, merged_rows,
    charuco_frame_numbers).
    """
    num_cameras = len(cameras)
    if len(all_rows) != num_cameras:
        raise ValueError(
            f"Detection count ({len(all_rows)}) != camera count ({num_cameras})"
        )

    logger.info(f"Calibrating {num_cameras} cameras")
    for cam_idx, (rows, camera) in enumerate(zip(all_rows, cameras)):
        logger.info(f"Camera {cam_idx} ({camera.id}): {len(rows)} frames with detections")
        if camera.image_size is None:
            raise ValueError(f"Camera '{camera.id}' has no image size")

    logger.info("Initializing camera intrinsics...")
    for cam_idx, (rows, camera) in enumerate(zip(all_rows, cameras)):
        objp, imgp = charuco_board_ops.get_all_calibration_points(board, rows)
        mixed = [(o, i) for (o, i) in zip(objp, imgp) if len(o) >= 7]
        if len(mixed) == 0:
            raise ValueError(f"No valid calibration points for camera {cam_idx} (need >= 7)")
        logger.info(f"  Camera {cam_idx}: {len(mixed)} usable frames")
        objp, imgp = zip(*mixed)
        matrix = cv2.initCameraMatrix2D(objp, imgp, tuple(camera.image_size))
        camera.intrinsics.fx = float(matrix[0, 0])
        camera.intrinsics.fy = float(matrix[1, 1])
        camera.intrinsics.cx = float(matrix[0, 2])
        camera.intrinsics.cy = float(matrix[1, 2])

    logger.info("Estimating board poses...")
    for i, (row, cam) in enumerate(zip(all_rows, cameras)):
        all_rows[i] = charuco_board_ops.estimate_pose_rows(board, cam, row)

    for cam_idx, (rows, camera) in enumerate(zip(all_rows, cameras)):
        valid_poses = sum(1 for r in rows if r.get("rvec") is not None and r.get("tvec") is not None)
        if valid_poses == 0:
            raise ValueError(
                f"Camera {cam_idx} ({camera.id}) has no frames with enough charuco corners "
                f"for pose estimation (need >= 6 per frame). "
                f"Ensure the charuco board is clearly visible and well-lit in every camera's view, "
                f"and that the correct board dimensions are configured."
            )
        logger.info(f"  Camera {cam_idx} ({camera.id}): {valid_poses}/{len(rows)} frames have valid board pose")

    charuco_frames = [f["framenum"][1] for f in all_rows[0]]

    logger.info("Merging observations across cameras...")
    cam_ids = camera_ids_from_camera_models(cameras)
    merged = merge_rows(all_rows=all_rows, camera_ids=cam_ids)

    image_points, board_observations = extract_points(merged, board, camera_ids=cam_ids, min_cameras=2)
    logger.info(f"Extracted points: shape={image_points.shape}")

    logger.info("Initializing camera extrinsics...")
    rtvecs = extract_roration_translation_vectors(merged, camera_ids=cam_ids)

    connections = get_connections(rtvecs, cam_ids)
    for (cam_a, cam_b), count in sorted(connections.items()):
        if cam_a < cam_b:
            logger.info(f"  {cam_a} <-> {cam_b}: {count} shared frames")

    rvecs, tvecs = get_initial_extrinsics(rtvecs, camera_ids=cam_ids)
    apply_extrinsics(cameras, rvecs, tvecs)

    logger.info("Starting iterative bundle adjustment...")
    error = iterative_bundle_adjustment(cameras, image_points, board_observations, error_threshold=1.0)
    logger.info(f"Calibration complete — final error: {error:.4f}")

    return error, merged, charuco_frames
