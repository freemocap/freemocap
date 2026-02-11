"""Top-level calibration pipeline.

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
from pathlib import Path

from .helpers.initialization import (
    initialize_board_poses,
    initialize_extrinsics,
    initialize_intrinsics,
)
from .helpers.models import (
    CalibrationResult,
    PyceresCalibrationSolverConfig,
    CameraModel,
    CharucoBoardDefinition,
    CharucoCornersObservation,
)
from .helpers.postprocessing import align_to_charuco_groundplane, pin_camera_to_origin
from .helpers.solver import run_bundle_adjustment
from .helpers.toml_io import save_calibration_toml

logger = logging.getLogger(__name__)


def run_pyceres_calibration(
    *,
    board: CharucoBoardDefinition,
    all_observations: list[CharucoCornersObservation],
    image_sizes: dict[str, tuple[int, int]],
    camera_names: list[str],
    config: PyceresCalibrationSolverConfig,
    output_toml_path: Path,
    use_groundplane: bool = False,
    extra_metadata: dict | None = None,
) -> CalibrationResult:
    """Run the complete camera calibration pipeline.

    Args:
        board: Charuco board definition.
        all_observations: All FrameObservation records across all cameras and frames.
        image_sizes: Per-camera image size as {name: (width, height)}.
        camera_names: Ordered list of camera names. Camera 0 is the reference.
        config: Solver configuration.
        output_toml_path: Where to save the calibration TOML.
        use_groundplane: If True, align the world frame to the charuco board plane.
        extra_metadata: Additional metadata to include in the TOML.

    Returns:
        CalibrationResult with optimized cameras.
    """
    # =========================================================================
    # VALIDATE INPUTS
    # =========================================================================
    if len(camera_names) < 2:
        raise ValueError(f"Need at least 2 cameras, got {len(camera_names)}")

    if len(all_observations) == 0:
        raise ValueError("No observations provided")

    for cam_name in camera_names:
        if cam_name not in image_sizes:
            raise KeyError(f"No image size for camera '{cam_name}'")

    # Group observations by camera
    observations_by_camera: dict[str, list[CharucoCornersObservation]] = {
        name: [] for name in camera_names
    }
    for obs in all_observations:
        if obs.camera_name not in observations_by_camera:
            raise ValueError(
                f"Observation references unknown camera '{obs.camera_name}'. "
                f"Known cameras: {camera_names}"
            )
        observations_by_camera[obs.camera_name].append(obs)

    for cam_name in camera_names:
        n_obs = len(observations_by_camera[cam_name])
        if n_obs == 0:
            raise ValueError(f"Camera '{cam_name}' has zero observations")
        logger.info(f"Camera '{cam_name}': {n_obs} frame observations")

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
        camera_names=camera_names,
    )

    # =========================================================================
    # STEP 3: BUILD INITIAL CAMERA MODELS
    # =========================================================================
    initial_cameras: list[CameraModel] = []
    for cam_name in camera_names:
        initial_cameras.append(
            CameraModel(
                name=cam_name,
                image_size=image_sizes[cam_name],
                intrinsics=intrinsics[cam_name],
                extrinsics=extrinsics[cam_name],
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

    result = run_bundle_adjustment(
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
        final_cameras = pin_camera_to_origin(
            cameras=final_cameras,
            camera_index=0,
        )

    if use_groundplane:
        try:
            final_cameras = align_to_charuco_groundplane(
                cameras=final_cameras,
                board=board,
                all_observations=all_observations,
            )
            if extra_metadata is None:
                extra_metadata = {}
            extra_metadata["groundplane_calibration"] = True
        except RuntimeError as e:
            logger.warning(f"Ground plane alignment failed: {e}")
            if extra_metadata is None:
                extra_metadata = {}
            extra_metadata["groundplane_calibration"] = False

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

    # =========================================================================
    # STEP 7: SAVE
    # =========================================================================
    logger.info("\n" + "=" * 80)
    logger.info("STEP 6: SAVE")
    logger.info("=" * 80)

    save_calibration_toml(
        result=result,
        path=output_toml_path,
        metadata=extra_metadata,
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
    logger.info(f"  Output:                {output_toml_path}")

    for cam in result.cameras:
        pos = cam.extrinsics.world_position
        logger.info(
            f"  Camera '{cam.name}': "
            f"pos=({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f})mm, "
            f"fx={cam.intrinsics.fx:.1f}, fy={cam.intrinsics.fy:.1f}"
        )

    return result
