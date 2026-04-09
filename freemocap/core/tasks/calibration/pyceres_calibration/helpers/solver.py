"""Bundle adjustment solver for camera calibration using pyceres.

Builds a pyceres optimization problem from camera models, board definition,
and 2D corner observations. Supports iterative outlier rejection.
"""

import logging
import time
from collections import defaultdict

import numpy as np
import pyceres
from numpy.typing import NDArray
from scipy.spatial.transform import Rotation

from freemocap.core.tasks.calibration.pyceres_calibration.helpers.cost_functions import CharucoReprojectionCost, \
    IntrinsicsPriorCost
from freemocap.core.tasks.calibration.pyceres_calibration.helpers.models import PyceresCalibrationSolverConfig
from freemocap.core.tasks.calibration.shared.calibration_models import CharucoBoardDefinition, CameraModel, \
    CharucoCornersObservation, CalibrationResult, CameraIntrinsics, CameraExtrinsics

logger = logging.getLogger(__name__)


# =============================================================================
# OBSERVATION INDEXING
# =============================================================================


class _ObservationRecord:
    """Tracks a single 2D observation and which parameter blocks it connects."""

    __slots__ = ("camera_name", "frame_index", "corner_id", "pixel_xy", "is_outlier")

    def __init__(
        self,
        *,
        camera_name: str,
        frame_index: int,
        corner_id: int,
        pixel_xy: NDArray[np.float64],
    ) -> None:
        self.camera_name = camera_name
        self.frame_index = frame_index
        self.corner_id = corner_id
        self.pixel_xy = pixel_xy.copy()
        self.is_outlier = False


# =============================================================================
# REPROJECTION ERROR COMPUTATION
# =============================================================================


def _compute_reprojection_errors(
    *,
    observations: list[_ObservationRecord],
    board: CharucoBoardDefinition,
    cam_quats: dict[str, NDArray[np.float64]],
    cam_trans: dict[str, NDArray[np.float64]],
    cam_intrinsics: dict[str, NDArray[np.float64]],
    board_quats: dict[int, NDArray[np.float64]],
    board_trans: dict[int, NDArray[np.float64]],
) -> NDArray[np.float64]:
    """Compute per-observation reprojection errors (in pixels).

    Returns array of shape (n_observations,) with pixel-space L2 error.
    """
    board_pts = board.corner_positions_board_frame
    errors = np.zeros(len(observations), dtype=np.float64)

    for idx, obs in enumerate(observations):
        cq = cam_quats[obs.camera_name]
        ct = cam_trans[obs.camera_name]
        ci = cam_intrinsics[obs.camera_name]
        bq = board_quats[obs.frame_index]
        bt = board_trans[obs.frame_index]

        # Board → world
        w, x, y, z = bq
        R_board = Rotation.from_quat([x, y, z, w]).as_matrix()
        p_world = R_board @ board_pts[obs.corner_id] + bt

        # World → camera
        w, x, y, z = cq
        R_cam = Rotation.from_quat([x, y, z, w]).as_matrix()
        p_cam = R_cam @ p_world + ct

        if p_cam[2] <= 1e-6:
            errors[idx] = 1e6
            continue

        # Project
        fx, fy, cx, cy, k1, k2, p1, p2 = ci
        xn = p_cam[0] / p_cam[2]
        yn = p_cam[1] / p_cam[2]
        r2 = xn * xn + yn * yn
        radial = 1.0 + k1 * r2 + k2 * r2 * r2
        xd = xn * radial + 2.0 * p1 * xn * yn + p2 * (r2 + 2.0 * xn * xn)
        yd = yn * radial + p1 * (r2 + 2.0 * yn * yn) + 2.0 * p2 * xn * yn
        u = fx * xd + cx
        v = fy * yd + cy

        diff = obs.pixel_xy - np.array([u, v])
        errors[idx] = np.linalg.norm(diff)

    return errors


# =============================================================================
# SOLVER
# =============================================================================


def run_pyceres_bundle_adjustment(
    *,
    cameras: list[CameraModel],
    board: CharucoBoardDefinition,
    all_observations: list[CharucoCornersObservation],
    board_poses_init: dict[int, tuple[NDArray[np.float64], NDArray[np.float64]]],
    config: PyceresCalibrationSolverConfig,
) -> CalibrationResult:
    """Run iterative bundle adjustment with outlier rejection.

    Args:
        cameras: Initial camera models (intrinsics + extrinsics).
        board: Charuco board definition.
        all_observations: All frame observations across all cameras.
        board_poses_init: Initial board poses {frame_idx: (quat_wxyz, translation)}.
        config: Solver configuration.

    Returns:
        CalibrationResult with optimized camera models.
    """
    t_start = time.monotonic()
    camera_name_to_idx = {cam.name: idx for idx, cam in enumerate(cameras)}
    board_pts_3d = board.corner_positions_board_frame

    # =========================================================================
    # BUILD OBSERVATION RECORDS
    # =========================================================================
    obs_records: list[_ObservationRecord] = []
    frame_indices_set: set[int] = set()

    for frame_obs in all_observations:
        cam_name = frame_obs.camera_name
        if cam_name not in camera_name_to_idx:
            raise ValueError(f"Observation references unknown camera '{cam_name}'")

        if frame_obs.n_corners < config.min_corners_per_frame:
            continue

        for corner in frame_obs.corners:
            if corner.corner_id < 0 or corner.corner_id >= board.n_corners:
                raise ValueError(
                    f"Corner ID {corner.corner_id} out of range [0, {board.n_corners})"
                )
            obs_records.append(
                _ObservationRecord(
                    camera_name=cam_name,
                    frame_index=frame_obs.frame_index,
                    corner_id=corner.corner_id,
                    pixel_xy=corner.pixel_xy,
                )
            )
            frame_indices_set.add(frame_obs.frame_index)

    if len(obs_records) == 0:
        raise ValueError("No valid observations after filtering")

    sorted_frame_indices = sorted(frame_indices_set)
    frame_idx_to_pos = {fi: pos for pos, fi in enumerate(sorted_frame_indices)}

    logger.info(f"Total observations: {len(obs_records)}")
    logger.info(f"Cameras: {len(cameras)}")
    logger.info(f"Board frames: {len(sorted_frame_indices)}")

    # Per-camera observation counts
    cam_obs_counts: dict[str, int] = defaultdict(int)
    for obs in obs_records:
        cam_obs_counts[obs.camera_name] += 1
    for cam in cameras:
        logger.info(f"  Camera '{cam.name}': {cam_obs_counts.get(cam.name, 0)} corner observations")

    # =========================================================================
    # ALLOCATE PARAMETER ARRAYS
    # =========================================================================
    n_cams = len(cameras)
    n_board_frames = len(sorted_frame_indices)

    # Camera parameters (persistent numpy arrays — modified in-place by Ceres)
    cam_quat_arrays: dict[str, NDArray[np.float64]] = {}
    cam_trans_arrays: dict[str, NDArray[np.float64]] = {}
    cam_intrinsics_arrays: dict[str, NDArray[np.float64]] = {}

    for cam in cameras:
        cam_quat_arrays[cam.name] = cam.extrinsics.quaternion_wxyz.copy()
        cam_trans_arrays[cam.name] = cam.extrinsics.translation.copy()
        cam_intrinsics_arrays[cam.name] = cam.intrinsics.to_param_array()

    # Board pose parameters
    board_quat_arrays: dict[int, NDArray[np.float64]] = {}
    board_trans_arrays: dict[int, NDArray[np.float64]] = {}

    for frame_idx in sorted_frame_indices:
        if frame_idx in board_poses_init:
            q, t = board_poses_init[frame_idx]
            board_quat_arrays[frame_idx] = q.copy()
            board_trans_arrays[frame_idx] = t.copy()
        else:
            board_quat_arrays[frame_idx] = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
            board_trans_arrays[frame_idx] = np.zeros(3, dtype=np.float64)

    # Save initial intrinsics for prior cost
    initial_intrinsics: dict[str, NDArray[np.float64]] = {
        cam.name: cam.intrinsics.to_param_array() for cam in cameras
    }

    # =========================================================================
    # ITERATIVE OUTLIER REJECTION
    # =========================================================================
    n_rejected_total = 0
    initial_cost = 0.0
    final_cost = 0.0
    total_iterations = 0

    n_outlier_iters = config.outlier_rejection_iterations
    thresholds = np.exp(
        np.linspace(
            np.log(config.initial_outlier_threshold_px),
            np.log(config.final_outlier_threshold_px),
            num=n_outlier_iters,
        )
    )

    for outlier_iter in range(n_outlier_iters):
        threshold = float(thresholds[outlier_iter])
        active_obs = [obs for obs in obs_records if not obs.is_outlier]

        if len(active_obs) == 0:
            raise RuntimeError(
                "All observations marked as outliers. "
                "Calibration data may be too noisy or initialization too far off."
            )

        logger.info(
            f"\n{'='*60}\n"
            f"Outlier iteration {outlier_iter + 1}/{n_outlier_iters} | "
            f"threshold={threshold:.2f}px | "
            f"active observations: {len(active_obs)}\n"
            f"{'='*60}"
        )

        # =====================================================================
        # BUILD CERES PROBLEM
        # =====================================================================
        problem = pyceres.Problem()

        # Register camera parameter blocks
        for cam in cameras:
            q_arr = cam_quat_arrays[cam.name]
            t_arr = cam_trans_arrays[cam.name]
            i_arr = cam_intrinsics_arrays[cam.name]

            problem.add_parameter_block(q_arr, 4)
            problem.set_manifold(q_arr, pyceres.QuaternionManifold())
            problem.add_parameter_block(t_arr, 3)
            problem.add_parameter_block(i_arr, 8)

            # Apply intrinsics optimization mode
            constant_indices = config.intrinsics_mode.constant_indices
            if len(constant_indices) == 8:
                problem.set_parameter_block_constant(i_arr)
            elif len(constant_indices) > 0:
                problem.set_manifold(
                    i_arr,
                    pyceres.SubsetManifold(8, constant_indices),
                )

        # Pin camera 0 extrinsics if configured
        if config.pin_camera_0:
            cam0 = cameras[0]
            problem.set_parameter_block_constant(cam_quat_arrays[cam0.name])
            problem.set_parameter_block_constant(cam_trans_arrays[cam0.name])

        # Register board pose parameter blocks
        for frame_idx in sorted_frame_indices:
            bq = board_quat_arrays[frame_idx]
            bt = board_trans_arrays[frame_idx]
            problem.add_parameter_block(bq, 4)
            problem.set_manifold(bq, pyceres.QuaternionManifold())
            problem.add_parameter_block(bt, 3)

        # Add reprojection cost for each active observation
        n_residuals_added = 0
        for obs in active_obs:
            cost = CharucoReprojectionCost(
                observed_pixel=obs.pixel_xy,
                board_point_3d=board_pts_3d[obs.corner_id],
                weight=1.0,
            )
            problem.add_residual_block(
                cost,
                pyceres.HuberLoss(threshold),  # Robust loss
                [
                    cam_quat_arrays[obs.camera_name],
                    cam_trans_arrays[obs.camera_name],
                    cam_intrinsics_arrays[obs.camera_name],
                    board_quat_arrays[obs.frame_index],
                    board_trans_arrays[obs.frame_index],
                ],
            )
            n_residuals_added += 1

        # Add intrinsics priors
        if config.intrinsics_prior_weight > 0:
            for cam in cameras:
                prior_cost = IntrinsicsPriorCost(
                    initial_intrinsics=initial_intrinsics[cam.name],
                    weight=config.intrinsics_prior_weight,
                )
                problem.add_residual_block(
                    prior_cost,
                    None,
                    [cam_intrinsics_arrays[cam.name]],
                )

        logger.info(f"Problem: {problem.num_residual_blocks()} residual blocks, "
                     f"{problem.num_parameters()} parameters")

        # =====================================================================
        # SOLVE
        # =====================================================================
        options = pyceres.SolverOptions()
        options.linear_solver_type = pyceres.LinearSolverType.SPARSE_SCHUR
        options.max_num_iterations = config.max_iterations
        options.function_tolerance = config.function_tolerance
        options.parameter_tolerance = config.parameter_tolerance
        options.gradient_tolerance = config.gradient_tolerance
        options.minimizer_progress_to_stdout = config.verbose

        summary = pyceres.SolverSummary()
        pyceres.solve(options, problem, summary)

        if outlier_iter == 0:
            initial_cost = summary.initial_cost

        final_cost = summary.final_cost
        total_iterations += summary.num_successful_steps

        logger.info(f"Solver: {summary.termination_type}")
        logger.info(f"  Initial cost: {summary.initial_cost:.4f}")
        logger.info(f"  Final cost:   {summary.final_cost:.4f}")
        logger.info(f"  Iterations:   {summary.num_successful_steps}")
        logger.info(f"  Time:         {summary.total_time_in_seconds:.2f}s")

        # =====================================================================
        # MARK OUTLIERS
        # =====================================================================
        if outlier_iter < n_outlier_iters - 1:
            errors = _compute_reprojection_errors(
                observations=obs_records,
                board=board,
                cam_quats=cam_quat_arrays,
                cam_trans=cam_trans_arrays,
                cam_intrinsics=cam_intrinsics_arrays,
                board_quats=board_quat_arrays,
                board_trans=board_trans_arrays,
            )

            n_newly_rejected = 0
            for idx, obs in enumerate(obs_records):
                if not obs.is_outlier and errors[idx] > threshold:
                    obs.is_outlier = True
                    n_newly_rejected += 1
                    n_rejected_total += 1

            active_errors = errors[~np.array([obs.is_outlier for obs in obs_records])]
            if len(active_errors) > 0:
                logger.info(
                    f"Reprojection error: "
                    f"median={np.median(active_errors):.3f}px, "
                    f"mean={np.mean(active_errors):.3f}px, "
                    f"max={np.max(active_errors):.3f}px"
                )
            logger.info(f"Rejected {n_newly_rejected} observations this iteration "
                         f"(total rejected: {n_rejected_total})")

    # =========================================================================
    # COMPUTE FINAL ERROR
    # =========================================================================
    final_errors = _compute_reprojection_errors(
        observations=[obs for obs in obs_records if not obs.is_outlier],
        board=board,
        cam_quats=cam_quat_arrays,
        cam_trans=cam_trans_arrays,
        cam_intrinsics=cam_intrinsics_arrays,
        board_quats=board_quat_arrays,
        board_trans=board_trans_arrays,
    )

    median_error = float(np.median(final_errors)) if len(final_errors) > 0 else float("inf")
    logger.info(f"\nFinal median reprojection error: {median_error:.4f} px")

    # =========================================================================
    # BUILD RESULT
    # =========================================================================
    result_cameras: list[CameraModel] = []
    for cam in cameras:
        new_intrinsics = CameraIntrinsics.from_param_array(cam_intrinsics_arrays[cam.name])

        quat = cam_quat_arrays[cam.name]
        trans = cam_trans_arrays[cam.name]
        new_extrinsics = CameraExtrinsics(
            quaternion_wxyz=quat.copy(),
            translation=trans.copy(),
        )

        result_cameras.append(
            CameraModel(
                name=cam.name,
                image_size=cam.image_size,
                intrinsics=new_intrinsics,
                extrinsics=new_extrinsics,
            )
        )

    elapsed = time.monotonic() - t_start
    n_used = sum(1 for obs in obs_records if not obs.is_outlier)

    return CalibrationResult(
        cameras=result_cameras,
        board=board,
        reprojection_error_px=median_error,
        initial_cost=initial_cost,
        final_cost=final_cost,
        n_iterations=total_iterations,
        time_seconds=elapsed,
        n_observations_used=n_used,
        n_observations_rejected=n_rejected_total,
    )
