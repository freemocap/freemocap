"""Anipose calibration post-processing helpers.

Pin camera 0 to origin, charuco groundplane alignment,
real-world camera position computation.
"""

import logging
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseRecorder
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.core.pipeline.posthoc.posthoc_calibration_task.anipose_calibration.helpers.freemocap_anipose import (
    AniposeCameraGroup,
    AniposeCharucoBoard,
)
from freemocap.core.pipeline.posthoc.posthoc_calibration_task.shared.groundplane_math import (
    CharucoVisibilityError,
    CharucoVelocityError,
    compute_board_basis_vectors,
    find_still_charuco_frame,
)
from freemocap.core.types.type_overloads import VideoIdString

logger = logging.getLogger(__name__)

CharucoObservations = dict[CameraIdString, CharucoObservation | None]


class GroundPlaneSuccess:
    def __init__(self, success: bool, error: str | None = None):
        self.success = success
        self.error = error


def interpolate_skeleton_data(skeleton_data: np.ndarray, method_to_use: str = "linear", order: int = 3) -> np.ndarray:
    """Interpolate missing NaN values in a 3D skeleton/charuco numpy array.

    Args:
        skeleton_data: (n_frames, n_markers, 3) array with possible NaN gaps.
        method_to_use: Pandas interpolation method (e.g. 'linear', 'polynomial').
        order: Order for polynomial/spline interpolation methods.

    Returns:
        Interpolated array with same shape, NaN gaps filled.
    """
    num_frames = skeleton_data.shape[0]
    num_markers = skeleton_data.shape[1]
    interpolated = np.empty((num_frames, num_markers, 3))

    for marker in range(num_markers):
        marker_data = skeleton_data[:, marker, :]
        df = pd.DataFrame(marker_data)
        df_interpolated = df.interpolate(method=method_to_use, axis=0, order=order)
        marker_array = np.array(df_interpolated)
        # Fill remaining NaNs (e.g. at recording start) with column mean
        marker_array = np.where(
            np.isfinite(marker_array),
            marker_array,
            np.nanmean(marker_array),
        )
        interpolated[:, marker, :] = marker_array

    return interpolated


def pin_camera_zero_to_origin(camera_group: AniposeCameraGroup) -> AniposeCameraGroup:
    """Re-express all camera extrinsics relative to camera 0.

    Camera 0 ends up with identity rotation and zero translation.
    All other cameras are expressed relative to camera 0.
    """
    rvecs_new = _align_rotations_to_cam0(camera_group=camera_group)
    camera_group.set_rotations(rvecs_new)
    tvecs_new = _shift_origin_to_cam0(camera_group=camera_group)
    camera_group.set_translations(tvecs_new)
    return camera_group


def _align_rotations_to_cam0(camera_group: AniposeCameraGroup) -> np.ndarray:
    """Align all camera rotations to camera 0's coordinate frame."""
    rvecs = camera_group.get_rotations()
    R0, _ = cv2.Rodrigues(rvecs[0])

    rvecs_new = np.empty_like(rvecs)
    for i in range(rvecs.shape[0]):
        Ri, _ = cv2.Rodrigues(rvecs[i])
        Ri_new, _ = cv2.Rodrigues(Ri @ R0.T)
        rvecs_new[i] = Ri_new.flatten()
    return rvecs_new


def _shift_origin_to_cam0(camera_group: AniposeCameraGroup) -> np.ndarray:
    """Shift world origin to camera 0's position."""
    tvecs = camera_group.get_translations()
    rvecs = camera_group.get_rotations()

    R0, _ = cv2.Rodrigues(rvecs[0, :])
    delta_to_origin_world = -R0.T @ tvecs[0, :]

    new_tvecs = np.zeros_like(tvecs)
    for cam_i in range(tvecs.shape[0]):
        Ri, _ = cv2.Rodrigues(rvecs[cam_i, :])
        delta_to_origin_camera_i = Ri @ delta_to_origin_world
        new_tvecs[cam_i, :] = tvecs[cam_i, :] + delta_to_origin_camera_i
    return new_tvecs


def set_charuco_board_as_groundplane(
    *,
    observation_recorders: dict[VideoIdString, BaseRecorder],
    anipose_camera_group: AniposeCameraGroup,
    anipose_charuco_board: AniposeCharucoBoard,
    recording_folder_path: "Path | None" = None,
) -> tuple[AniposeCameraGroup, GroundPlaneSuccess]:
    """Set the charuco board plane as the world groundplane."""
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
    charuco_3d_flat = anipose_camera_group.triangulate(charuco_2d_flat)
    charuco3d_fr_id_xyz = charuco_3d_flat.reshape(num_frames, num_tracked_points, 3)
    logger.info(f"Charuco 3d data reconstructed with shape: {charuco3d_fr_id_xyz.shape}")

    charuco_3d_xyz_interpolated = interpolate_skeleton_data(skeleton_data=charuco3d_fr_id_xyz)

    try:
        charuco_still_frame_idx = find_still_charuco_frame(
            charuco_3d=charuco3d_fr_id_xyz,
            squares_x=anipose_charuco_board.squaresX,
            squares_y=anipose_charuco_board.squaresY,
        )
    except CharucoVisibilityError as e:
        logger.warning("Ground-plane alignment skipped — reverting to original calibration: %s", e, exc_info=True)
        return anipose_camera_group, GroundPlaneSuccess(success=False, error=str(e))
    except CharucoVelocityError as e:
        logger.warning("Ground-plane alignment skipped — reverting to original calibration: %s", e, exc_info=True)
        return anipose_camera_group, GroundPlaneSuccess(success=False, error=str(e))

    charuco_frame = charuco_3d_xyz_interpolated[charuco_still_frame_idx]

    x_hat, y_hat, z_hat = compute_board_basis_vectors(
        charuco_frame=charuco_frame,
        squares_x=anipose_charuco_board.squaresX,
        squares_y=anipose_charuco_board.squaresY,
    )

    charuco_origin_in_world = charuco_frame[0]
    rmat_charuco_to_world = np.column_stack([x_hat, y_hat, z_hat])

    rvecs_new, tvecs_new = _adjust_world_reference_frame_to_charuco(
        camera_group=anipose_camera_group,
        charuco_origin_in_world=charuco_origin_in_world,
        rmat_charuco_to_world=rmat_charuco_to_world,
    )

    anipose_camera_group.set_rotations(rvecs_new)
    anipose_camera_group.set_translations(tvecs_new)

    logger.info("Anipose camera calibration data adjusted to set charuco board as ground plane")

    # Recalculate 3D charuco data in new coordinate system
    charuco_3d_flat = anipose_camera_group.triangulate(charuco_2d_flat)
    charuco3d_fr_id_xyz = charuco_3d_flat.reshape(num_frames, num_tracked_points, 3)
    charuco_3d_xyz_interpolated = interpolate_skeleton_data(skeleton_data=charuco3d_fr_id_xyz)

    if recording_folder_path is not None:
        charuco_save_path = Path(recording_folder_path) / "output_data" / "charuco_3d_xyz.npy"
        charuco_save_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(charuco_save_path, charuco_3d_xyz_interpolated)
        logger.info(f"Charuco 3d data saved to {charuco_save_path}")

    return anipose_camera_group, GroundPlaneSuccess(success=True)


def _adjust_world_reference_frame_to_charuco(
    *,
    camera_group: AniposeCameraGroup,
    charuco_origin_in_world: np.ndarray,
    rmat_charuco_to_world: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Adjust camera extrinsics to use charuco board as world reference frame."""
    tvecs = camera_group.get_translations()
    rvecs = camera_group.get_rotations()

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


def get_real_world_matrices(camera_group: AniposeCameraGroup) -> tuple[list, list]:
    """Calculate real-world positions and orientations of cameras."""
    rvecs = camera_group.get_rotations()
    tvecs = camera_group.get_translations()

    positions = []
    orientations = []

    for i in range(tvecs.shape[0]):
        rmat_world_to_cam_i, _ = cv2.Rodrigues(rvecs[i])
        rmat_cam_to_world = rmat_world_to_cam_i.T
        t_world = -rmat_cam_to_world @ tvecs[i]

        positions.append(t_world.astype(float).tolist())
        orientations.append(rmat_cam_to_world.astype(float).tolist())

    camera_group.set_world_positions(positions)
    camera_group.set_world_orientations(orientations)

    return positions, orientations
