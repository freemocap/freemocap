"""Anipose calibration post-processing helpers.

Pin camera 0 to origin, charuco groundplane alignment,
real-world camera position computation — all operating on list[CameraModel].
"""

import logging
from pathlib import Path

import cv2
import numpy as np
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseRecorder
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.core.tasks.calibration.anipose_calibration.helpers.camera_model_solver_ops import (
    apply_extrinsics,
    stack_rodrigues,
    stack_translations,
)
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel
from skellytracker.trackers.charuco_tracker import CharucoBoardDefinition
from freemocap.core.tasks.calibration.shared.groundplane_alignment import GroundPlaneResult
from freemocap.core.tasks.calibration.shared.groundplane_math import (
    CharucoVelocityError,
    CharucoVisibilityError,
    compute_board_basis_vectors,
    find_still_charuco_frame,
)
from freemocap.core.tasks.calibration.shared.interpolate_trajectories import interpolate_trajectory_data
from freemocap.core.types.type_overloads import VideoIdString

logger = logging.getLogger(__name__)

CharucoObservations = dict[CameraIdString, CharucoObservation | None]


class GroundPlaneSuccess:
    def __init__(self, success: bool, error: str | None = None):
        self.success = success
        self.error = error


def pin_camera_zero_to_origin(cameras: list[CameraModel]) -> list[CameraModel]:
    """Re-express all camera extrinsics relative to camera 0.

    Camera 0 ends up with identity rotation and zero translation.
    All other cameras are expressed relative to camera 0.
    """
    rvecs = stack_rodrigues(cameras)
    tvecs = stack_translations(cameras)

    R0, _ = cv2.Rodrigues(rvecs[0])
    rvecs_new = np.empty_like(rvecs)
    for i in range(rvecs.shape[0]):
        Ri, _ = cv2.Rodrigues(rvecs[i])
        Ri_new, _ = cv2.Rodrigues(Ri @ R0.T)
        rvecs_new[i] = Ri_new.flatten()

    # Use R0_new (identity for camera 0 after alignment) — not original R0
    R0_new, _ = cv2.Rodrigues(rvecs_new[0])
    delta_to_origin_world = -R0_new.T @ tvecs[0, :]
    tvecs_new = np.zeros_like(tvecs)
    for cam_i in range(tvecs.shape[0]):
        Ri, _ = cv2.Rodrigues(rvecs_new[cam_i])
        delta_to_origin_camera_i = Ri @ delta_to_origin_world
        tvecs_new[cam_i, :] = tvecs[cam_i, :] + delta_to_origin_camera_i

    apply_extrinsics(cameras, rvecs_new, tvecs_new)
    return cameras


def set_charuco_board_as_groundplane(
    *,
    observation_recorders: dict[VideoIdString, BaseRecorder],
    cameras: list[CameraModel],
    board: CharucoBoardDefinition,
    recording_folder_path: "Path | None" = None,
) -> tuple[list[CameraModel], GroundPlaneSuccess, GroundPlaneResult | None]:
    """Set the charuco board plane as the world groundplane."""
    from freemocap.core.tasks.calibration.anipose_calibration.helpers.bundle_adjust import triangulate

    logger.info("Getting 2D Charuco data")
    data2d_by_video: dict[VideoIdString, np.ndarray] = {}
    if len(observation_recorders) == 0:
        raise ValueError("No observation recorders provided to process.")

    for video_id, recorder in observation_recorders.items():
        if not all(isinstance(observation, CharucoObservation) for observation in recorder.observations):
            raise TypeError(f"Recorder for video ID {video_id} contains non-Charuco observations.")
        data2d_fr_id_xyc = recorder.to_array.copy()
        logger.info(f"Processing video ID: {video_id} with 2D data shape: {data2d_fr_id_xyc.shape}")
        data2d_by_video[video_id] = data2d_fr_id_xyc[..., :2]

    charuco2d_cam_fr_id_xy = np.stack(list(data2d_by_video.values()), axis=0)
    logger.info(
        f"Charuco 2d data retrieved with shape (cams, frames, markers, XY): {charuco2d_cam_fr_id_xy.shape}"
    )
    charuco2d_cam_fr_id_xy = charuco2d_cam_fr_id_xy.astype(np.float64)
    num_cameras, num_frames, num_tracked_points, _ = charuco2d_cam_fr_id_xy.shape
    charuco_2d_flat = charuco2d_cam_fr_id_xy.reshape(num_cameras, -1, 2)

    logger.info("Getting 3d Charuco data")
    charuco_3d_flat = triangulate(cameras, charuco_2d_flat)
    charuco3d_fr_id_xyz = charuco_3d_flat.reshape(num_frames, num_tracked_points, 3)
    logger.info(f"Charuco 3d data reconstructed with shape: {charuco3d_fr_id_xyz.shape}")

    charuco_3d_xyz_interpolated = interpolate_trajectory_data(trajectory_data=charuco3d_fr_id_xyz)

    try:
        charuco_still_frame_idx = find_still_charuco_frame(
            charuco_3d=charuco3d_fr_id_xyz,
            squares_x=board.squares_x,
            squares_y=board.squares_y,
        )
    except CharucoVisibilityError as e:
        logger.warning("Ground-plane alignment skipped — reverting to original calibration: %s", e, exc_info=True)
        return cameras, GroundPlaneSuccess(success=False, error=str(e)), None
    except CharucoVelocityError as e:
        logger.warning("Ground-plane alignment skipped — reverting to original calibration: %s", e, exc_info=True)
        return cameras, GroundPlaneSuccess(success=False, error=str(e)), None

    charuco_frame = charuco_3d_xyz_interpolated[charuco_still_frame_idx]

    x_hat, y_hat, z_hat = compute_board_basis_vectors(
        charuco_frame=charuco_frame,
        squares_x=board.squares_x,
        squares_y=board.squares_y,
    )

    charuco_origin_in_world = charuco_frame[0]
    rmat_charuco_to_world = np.column_stack([x_hat, y_hat, z_hat])

    ground_plane_result = GroundPlaneResult(
        origin=charuco_origin_in_world,
        rotation_matrix=rmat_charuco_to_world,
        method="charuco",
    )

    rvecs_new, tvecs_new = _adjust_world_reference_frame_to_charuco(
        cameras=cameras,
        charuco_origin_in_world=charuco_origin_in_world,
        rmat_charuco_to_world=rmat_charuco_to_world,
    )
    apply_extrinsics(cameras, rvecs_new, tvecs_new)

    logger.info("Camera calibration adjusted to set charuco board as ground plane")

    charuco_3d_flat = triangulate(cameras, charuco_2d_flat)
    charuco3d_fr_id_xyz = charuco_3d_flat.reshape(num_frames, num_tracked_points, 3)
    charuco_3d_xyz_interpolated = interpolate_trajectory_data(trajectory_data=charuco3d_fr_id_xyz)

    if recording_folder_path is not None:
        charuco_save_path = Path(recording_folder_path) / "output_data" / "charuco_3d_xyz.npy"
        charuco_save_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(charuco_save_path, charuco_3d_xyz_interpolated)
        logger.info(f"Charuco 3d data saved to {charuco_save_path}")

    return cameras, GroundPlaneSuccess(success=True), ground_plane_result


def _adjust_world_reference_frame_to_charuco(
    *,
    cameras: list[CameraModel],
    charuco_origin_in_world: np.ndarray,
    rmat_charuco_to_world: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Adjust camera extrinsics to use charuco board as world reference frame."""
    rvecs = stack_rodrigues(cameras)
    tvecs = stack_translations(cameras)

    tvecs_new = np.zeros_like(tvecs)
    rvecs_new = np.zeros_like(rvecs)

    for i in range(tvecs.shape[0]):
        rmat_world_to_cam_i, _ = cv2.Rodrigues(rvecs[i])
        t_delta = rmat_world_to_cam_i @ charuco_origin_in_world
        tvecs_new[i] = t_delta + tvecs[i]

        new_rmat = rmat_world_to_cam_i @ rmat_charuco_to_world
        new_rvec, _ = cv2.Rodrigues(new_rmat)
        rvecs_new[i] = new_rvec.flatten()

    return rvecs_new, tvecs_new


# Keep old names as aliases for backward compatibility within this module.
# (run_anipose_calibration.py is updated separately.)
anipose_pin_camera_zero_to_origin = pin_camera_zero_to_origin
set_charuco_board_as_groundplane_anipose = set_charuco_board_as_groundplane
