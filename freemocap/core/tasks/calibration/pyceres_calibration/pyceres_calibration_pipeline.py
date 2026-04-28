"""Top-level pyceres calibration pipeline.

Orchestrates the full calibration flow:
  1. Validate and organize observations
  2. Initialize intrinsics (per-camera cv2.calibrateCamera)
  3. Initialize extrinsics (pairwise transforms → spanning tree)
  4. Initialize board poses (per-frame solvePnP → world transform)
  5. Bundle adjustment (pyceres with iterative outlier rejection)
  6. Post-processing (pin to origin, optional groundplane alignment)
  7. Save results
"""

import logging

from freemocap.core.tasks.calibration.pyceres_calibration.helpers.initialization import initialize_intrinsics, \
    initialize_extrinsics, initialize_board_poses
from freemocap.core.tasks.calibration.pyceres_calibration.helpers.models import PyceresCalibrationSolverConfig
from freemocap.core.tasks.calibration.pyceres_calibration.helpers.postprocessing import pin_camera_to_origin, \
    align_to_charuco_groundplane
from freemocap.core.tasks.calibration.pyceres_calibration.helpers.solver import run_pyceres_bundle_adjustment
from freemocap.core.tasks.calibration.shared.calibration_models import CharucoBoardDefinition, \
    CharucoCornersObservation, \
    CalibrationResult, CameraModel
from freemocap.core.tasks.calibration.shared.groundplane_alignment import GroundPlaneResult

logger = logging.getLogger(__name__)


def run_pyceres_calibration(
    *,
    board: CharucoBoardDefinition,
    all_observations: list[CharucoCornersObservation],
    image_sizes: dict[str, tuple[int, int]],
    camera_ids: list[str],
    config: PyceresCalibrationSolverConfig,
    use_groundplane: bool = False,
) -> tuple[CalibrationResult, GroundPlaneResult | None]:
    """Run the complete camera calibration pipeline.

    Args:
        board: Charuco board definition.
        all_observations: All FrameObservation records across all cameras and frames.
        image_sizes: Per-camera image size as {name: (width, height)}.
        camera_ids: Ordered list of camera names. Camera 0 is the reference.
        config: Solver configuration.
        use_groundplane: If True, align the world frame to the charuco board plane.

    Returns:
        CalibrationResult with optimized cameras. Caller is responsible for saving.
    """
    # =========================================================================
    # VALIDATE INPUTS
    # =========================================================================
    if len(camera_ids) < 2:
        raise ValueError(f"Need at least 2 cameras, got {len(camera_ids)}")

    if len(all_observations) == 0:
        raise ValueError("No observations provided")

    for camera_id in camera_ids:
        if camera_id not in image_sizes:
            raise KeyError(f"No image size for camera '{camera_id}'")

    # Group observations by camera
    observations_by_camera: dict[str, list[CharucoCornersObservation]] = {
        name: [] for name in camera_ids
    }
    for obs in all_observations:
        if obs.camera_name not in observations_by_camera:
            raise ValueError(
                f"Observation references unknown camera '{obs.camera_name}'. "
                f"Known cameras: {camera_ids}"
            )
        observations_by_camera[obs.camera_name].append(obs)

    for camera_id in camera_ids:
        n_obs = len(observations_by_camera[camera_id])
        if n_obs == 0:
            raise ValueError(f"Camera '{camera_id}' has zero observations")
        logger.info(f"Camera '{camera_id}': {n_obs} frame observations")

    # =========================================================================
    # STEP 1: INITIALIZE INTRINSICS
    # =========================================================================
    logger.info("\n" + "=" * 80)
    logger.info("STEP 1: INITIALIZE INTRINSICS")
    logger.info("=" * 80)

    intrinsics = initialize_intrinsics(
        board=board,
        observations_by_camera=observations_by_camera,
        image_sizes=image_sizes,
    )

    # =========================================================================
    # STEP 2: INITIALIZE EXTRINSICS
    # =========================================================================
    logger.info("\n" + "=" * 80)
    logger.info("STEP 2: INITIALIZE EXTRINSICS")
    logger.info("=" * 80)

    extrinsics = initialize_extrinsics(
        board=board,
        observations_by_camera=observations_by_camera,
        intrinsics=intrinsics,
        camera_names=camera_ids,
    )

    # =========================================================================
    # STEP 3: BUILD INITIAL CAMERA MODELS
    # =========================================================================
    initial_cameras: list[CameraModel] = []
    for camera_id in camera_ids:
        initial_cameras.append(
            CameraModel(
                id=camera_id,
                image_size=image_sizes[camera_id],
                intrinsics=intrinsics[camera_id],
                extrinsics=extrinsics[camera_id],
            )
        )

    # =========================================================================
    # STEP 4: INITIALIZE BOARD POSES
    # =========================================================================
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: INITIALIZE BOARD POSES")
    logger.info("=" * 80)

    all_frame_indices = sorted({obs.frame_index for obs in all_observations})
    board_poses_init = initialize_board_poses(
        board=board,
        observations_by_camera=observations_by_camera,
        intrinsics=intrinsics,
        extrinsics=extrinsics,
        all_frame_indices=all_frame_indices,
    )

    # =========================================================================
    # STEP 5: BUNDLE ADJUSTMENT
    # =========================================================================
    logger.info("\n" + "=" * 80)
    logger.info("STEP 4: BUNDLE ADJUSTMENT")
    logger.info("=" * 80)

    result = run_pyceres_bundle_adjustment(
        cameras=initial_cameras,
        board=board,
        all_observations=all_observations,
        board_poses_init=board_poses_init,
        config=config,
    )

    # =========================================================================
    # STEP 6: POST-PROCESSING
    # =========================================================================
    logger.info("\n" + "=" * 80)
    logger.info("STEP 5: POST-PROCESSING")
    logger.info("=" * 80)

    final_cameras = result.cameras

    if config.pin_camera_0:
        pin_camera_id = config.pin_camera_id or final_cameras[0].id
        final_cameras = pin_camera_to_origin(
            cameras=final_cameras,
            camera_id=pin_camera_id,
        )

    ground_plane_result: GroundPlaneResult | None = None
    if use_groundplane:
        try:
            final_cameras, ground_plane_result = align_to_charuco_groundplane(
                cameras=final_cameras,
                board=board,
                all_observations=all_observations,
            )
        except RuntimeError as e:
            logger.warning(f"Ground plane alignment failed: {e}")

    # Rebuild result with post-processed cameras
    result = CalibrationResult(
        cameras=final_cameras,
        board=result.board,
        reprojection_error_px=result.reprojection_error_px,
        initial_cost=result.initial_cost,
        final_cost=result.final_cost,
        n_iterations=result.n_iterations,
        time_seconds=result.time_seconds,
        n_observations_used=result.n_observations_used,
        n_observations_rejected=result.n_observations_rejected,
    )

    # Log final summary
    logger.info("\n" + "=" * 80)
    logger.info("CALIBRATION COMPLETE")
    logger.info("=" * 80)
    logger.info(f"  Cameras:               {len(result.cameras)}")
    logger.info(f"  Reprojection error:    {result.reprojection_error_px:.4f} px")
    logger.info(f"  Observations used:     {result.n_observations_used}")
    logger.info(f"  Observations rejected: {result.n_observations_rejected}")
    logger.info(f"  Solver time:           {result.time_seconds:.2f}s")

    for cam in result.cameras:
        pos = cam.extrinsics.world_position
        logger.info(
            f"  Camera '{cam.name}': "
            f"pos=({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f})mm, "
            f"fx={cam.intrinsics.fx:.1f}, fy={cam.intrinsics.fy:.1f}"
        )

    return result, ground_plane_result
