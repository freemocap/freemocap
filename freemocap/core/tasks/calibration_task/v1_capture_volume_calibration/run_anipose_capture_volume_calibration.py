import logging
from pathlib import Path

import cv2
import numpy as np
from pydantic import BaseModel, Field

from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.tasks.calibration_task.v1_capture_volume_calibration.anipose_camera_calibration.freemocap_anipose import (
    CameraGroup, AniposeCharucoBoard
)
from freemocap.core_processes.capture_volume_calibration.anipose_camera_calibration.charuco_groundplane_utils import (
    compute_basis_vectors_of_new_reference,
    find_good_frame,
    skellyforge_data,
    CharucoVisibilityError,
    CharucoVelocityError
)
from freemocap.system.paths_and_filenames.path_getters import (
    create_camera_calibration_file_name,
    get_calibrations_folder_path,
    get_last_successful_calibration_toml_path,
)

logger = logging.getLogger(__name__)

CharucoObservations = dict[CameraIdString, CharucoObservation | None]


class CharucoObservationAggregator(BaseModel):
    anipose_camera_ordering: list[CameraIdString]
    # anipose handles camera rows by the ordering of cameras in CameraGroup - so we need to use that ordering when we pass the camera rows to anipose
    individual_camera_rows: dict[CameraIdString, list] = Field(default_factory=dict)

    @classmethod
    def from_charuco_observation_payload(cls,
                                         charuco_observations_by_camera: CharucoObservations,
                                         anipose_camera_ordering: list[CameraIdString]):
        if set(charuco_observations_by_camera.keys()) != set(anipose_camera_ordering):
            raise ValueError("individual_camera_rows and anipose_camera_ordering must have the same camera ids")
        camera_rows = {}
        for camera_id, charuco_observation in charuco_observations_by_camera.items():
            anipose_camera_row = charuco_observation.to_anipose_camera_row() if charuco_observation is not None else None
            camera_rows[camera_id] = [anipose_camera_row] if anipose_camera_row is not None else []

        return cls(individual_camera_rows=camera_rows, anipose_camera_ordering=anipose_camera_ordering)

    @property
    def all_camera_rows(self):
        return [self.individual_camera_rows[anipose_camera_id] for anipose_camera_id in self.anipose_camera_ordering]

    def add_observations(self, charuco_observations_by_camera: CharucoObservations):
        for camera_id, charuco_observation in charuco_observations_by_camera.items():
            anipose_camera_row = charuco_observation.to_anipose_camera_row() if charuco_observation is not None else None
            if anipose_camera_row is not None:
                self.individual_camera_rows[camera_id].append(anipose_camera_row)


class GroundPlaneSuccess:
    def __init__(self, success: bool, error: str | None = None):
        self.success = success
        self.error = error


def anipose_calibration_from_charuco_observations(
        charuco_observations_by_frame: list[CharucoObservations],
        charuco_board: AniposeCharucoBoard,
        camera_group: CameraGroup,
        recording_name: str,
        calibration_toml_save_path: Path | str,
        recording_folder_path: Path | str | None = None,
        pin_camera_0_to_origin: bool = False,
        use_charuco_as_groundplane: bool = False,
        init_intrinsics: bool = True,
        init_extrinsics: bool = True,
        verbose: bool = True,
        **kwargs
) -> tuple[Path, GroundPlaneSuccess | None]:
    """
    Perform full camera calibration from charuco observations including groundplane correction and TOML export.

    Args:
        charuco_observations_by_frame: List of observations for each frame, keyed by camera ID
        charuco_board: AniposeCharucoBoard instance defining the calibration board
        camera_group: CameraGroup instance with camera definitions
        recording_name: Name of the recording session for filename generation
        calibration_toml_save_path: Primary path where calibration TOML will be saved
        recording_folder_path: Optional path to recording folder for saving a copy
        pin_camera_0_to_origin: Whether to set camera 0 as the origin
        use_charuco_as_groundplane: Whether to use charuco board as groundplane reference
        init_intrinsics: Whether to initialize camera intrinsics
        init_extrinsics: Whether to initialize camera extrinsics
        verbose: Whether to print verbose output
        **kwargs: Additional arguments passed to calibrate_rows

    Returns:
        Tuple of (calibration_toml_path, groundplane_success)
    """
    # Aggregate all observations
    charuco_observation_aggregator: CharucoObservationAggregator | None = None
    for charuco_observations_by_camera in charuco_observations_by_frame:
        if charuco_observation_aggregator is None:
            charuco_observation_aggregator = CharucoObservationAggregator.from_charuco_observation_payload(
                charuco_observations_by_camera=charuco_observations_by_camera,
                anipose_camera_ordering=[camera.name for camera in camera_group.cameras])
        else:
            charuco_observation_aggregator.add_observations(charuco_observations_by_camera)

    if charuco_observation_aggregator is None:
        raise ValueError("No charuco observations were provided for calibration")

    # Perform calibration on aggregated rows
    all_camera_rows = charuco_observation_aggregator.all_camera_rows
    error, merged, charuco_frame_numbers = camera_group.calibrate_rows(
        all_camera_rows,
        charuco_board,
        init_intrinsics=init_intrinsics,
        init_extrinsics=init_extrinsics,
        verbose=verbose,
        **kwargs
    )

    success_str = "Anipose Calibration Successful!"
    logger.info(success_str)
    logger.info(f"Calibration error: {error}")

    camera_group.metadata["groundplane_calibration"] = False
    groundplane_success: GroundPlaneSuccess | None = None

    # Apply camera 0 pinning if requested
    if pin_camera_0_to_origin:
        camera_group = pin_camera_zero_to_origin(camera_group=camera_group)
        logger.info("Pinned camera 0 to origin")

    # Apply groundplane correction if requested
    if use_charuco_as_groundplane:
        camera_group, groundplane_success = set_charuco_board_as_groundplane(
            camera_group=camera_group,
            charuco_board=charuco_board,
            recording_folder_path=Path(recording_folder_path) if recording_folder_path else None
        )
        if groundplane_success.success:
            camera_group.metadata["groundplane_calibration"] = True
            logger.info("Successfully set charuco board as groundplane")
        else:
            logger.warning(f"Failed to set groundplane: {groundplane_success.error}")

    # Calculate real-world camera positions and orientations
    get_real_world_matrices(camera_group=camera_group)

    # Create calibration filename
    calibration_toml_filename = create_camera_calibration_file_name(recording_name=recording_name)

    # Save to main calibration folder
    calibration_folder_toml_path = Path(get_calibrations_folder_path()) / calibration_toml_filename
    camera_group.dump(calibration_folder_toml_path)
    logger.info(f"Saved calibration to: {calibration_folder_toml_path}")

    # Save to recording folder if provided
    if recording_folder_path is not None:
        recording_folder_toml_path = Path(recording_folder_path) / calibration_toml_filename
        camera_group.dump(recording_folder_toml_path)
        logger.info(f"Saved calibration copy to recording folder: {recording_folder_toml_path}")

    # Save as last successful calibration
    last_successful_calibration_toml_path = get_last_successful_calibration_toml_path()
    camera_group.dump(last_successful_calibration_toml_path)
    logger.info(f"Saved as last successful calibration: {last_successful_calibration_toml_path}")

    return calibration_folder_toml_path, groundplane_success


def pin_camera_zero_to_origin(camera_group: CameraGroup) -> CameraGroup:
    """
    Re-express all camera extrinsics relative to camera 0.

    This function performs two operations:
        1. Rotates all camera coordinate systems so that camera 0's orientation becomes the new world frame.
        2. Shifts the world origin to camera 0's position, making it the new coordinate origin (0, 0, 0).

    The result is that:
        - Camera 0 ends up with an identity rotation and zero translation.
        - All other cameras are expressed relative to camera 0's original position and orientation.
    """
    rvecs_new = align_rotations_to_cam0(camera_group=camera_group)
    camera_group.set_rotations(rvecs_new)
    tvecs_new = shift_origin_to_cam0(camera_group=camera_group)
    camera_group.set_translations(tvecs_new)
    return camera_group


def align_rotations_to_cam0(camera_group: CameraGroup) -> np.ndarray:
    """Align all camera rotations to camera 0's coordinate frame."""
    rvecs = camera_group.get_rotations()
    R0, _ = cv2.Rodrigues(rvecs[0])

    rvecs_new = np.empty_like(rvecs)
    for i in range(rvecs.shape[0]):
        Ri, _ = cv2.Rodrigues(rvecs[i])
        Ri_new, _ = cv2.Rodrigues(Ri @ R0.T)
        rvecs_new[i] = Ri_new.flatten()
    return rvecs_new


def shift_origin_to_cam0(camera_group: CameraGroup) -> np.ndarray:
    """Shift world origin to camera 0's position."""
    tvecs = camera_group.get_translations()
    rvecs = camera_group.get_rotations()

    camera_0_translation = tvecs[0, :]
    camera_0_rotation = rvecs[0, :]

    R0, _ = cv2.Rodrigues(camera_0_rotation)
    delta_to_origin_world = -R0.T @ camera_0_translation

    new_tvecs = np.zeros_like(tvecs)
    for cam_i in range(tvecs.shape[0]):
        Ri, _ = cv2.Rodrigues(rvecs[cam_i, :])
        delta_to_origin_camera_i = Ri @ delta_to_origin_world
        new_tvecs[cam_i, :] = tvecs[cam_i, :] + delta_to_origin_camera_i
    return new_tvecs


def set_charuco_board_as_groundplane(
        camera_group: CameraGroup,
        charuco_board: AniposeCharucoBoard,
        recording_folder_path: Path | None = None
) -> tuple[CameraGroup, GroundPlaneSuccess]:
    """Set the charuco board plane as the world groundplane."""
    logger.info("Getting 2D Charuco data")

    charuco_2d_xy: np.ndarray = camera_group.charuco_2d_data

    if charuco_2d_xy is None:
        error_message = "Charuco 2d data was not retrieved successfully. Check for an error during calibration."
        logger.error(error_message)
        raise ValueError(error_message)

    logger.info(f"Charuco 2d data retrieved successfully with shape: {charuco_2d_xy.shape}")
    charuco_2d_xy = charuco_2d_xy.astype(np.float64)
    num_cameras, num_frames, num_tracked_points, _ = charuco_2d_xy.shape
    charuco_2d_flat = charuco_2d_xy.reshape(num_cameras, -1, 2)

    logger.info("Getting 3d Charuco data")
    charuco_3d_flat = camera_group.triangulate(charuco_2d_flat)
    charuco_3d_xyz = charuco_3d_flat.reshape(num_frames, num_tracked_points, 3)
    logger.info(f"Charuco 3d data reconstructed with shape: {charuco_3d_xyz.shape}")

    charuco_3d_xyz_interpolated = skellyforge_data(raw_charuco_data=charuco_3d_xyz)

    try:
        charuco_still_frame_idx = find_good_frame(
            charuco_data=charuco_3d_xyz_interpolated,
            number_of_squares_width=charuco_board.squaresX,
            number_of_squares_height=charuco_board.squaresY,
        )
    except CharucoVisibilityError as e:
        logger.warning("Ground-plane alignment skipped — reverting to original calibration: %s", e, exc_info=True)
        return camera_group, GroundPlaneSuccess(success=False, error=str(e))
    except CharucoVelocityError as e:
        logger.warning("Ground-plane alignment skipped — reverting to original calibration: %s", e, exc_info=True)
        return camera_group, GroundPlaneSuccess(success=False, error=str(e))

    charuco_frame = charuco_3d_xyz_interpolated[charuco_still_frame_idx]

    x_hat, y_hat, z_hat = compute_basis_vectors_of_new_reference(
        charuco_frame,
        number_of_squares_width=charuco_board.squaresX,
        number_of_squares_height=charuco_board.squaresY
    )

    charuco_origin_in_world = charuco_frame[0]
    rmat_charuco_to_world = np.column_stack([x_hat, y_hat, z_hat])

    rvecs_new, tvecs_new = adjust_world_reference_frame_to_charuco(
        camera_group=camera_group,
        charuco_origin_in_world=charuco_origin_in_world,
        rmat_charuco_to_world=rmat_charuco_to_world
    )

    camera_group.set_rotations(rvecs_new)
    camera_group.set_translations(tvecs_new)

    logger.info("Anipose camera calibration data adjusted to set charuco board as ground plane")

    # Recalculate 3D charuco data in new coordinate system
    charuco_3d_flat = camera_group.triangulate(charuco_2d_flat)
    charuco_3d_xyz = charuco_3d_flat.reshape(num_frames, num_tracked_points, 3)
    charuco_3d_xyz_interpolated = skellyforge_data(raw_charuco_data=charuco_3d_xyz)

    # Save charuco 3D data if recording folder is provided
    if recording_folder_path is not None:
        charuco_save_path = recording_folder_path / "output_data" / "charuco_3d_xyz.npy"
        charuco_save_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(charuco_save_path, charuco_3d_xyz_interpolated)
        logger.info(f"Charuco 3d data saved to {charuco_save_path}")

    return camera_group, GroundPlaneSuccess(success=True)


def adjust_world_reference_frame_to_charuco(
        camera_group: CameraGroup,
        charuco_origin_in_world: np.ndarray,
        rmat_charuco_to_world: np.ndarray
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


def get_real_world_matrices(camera_group: CameraGroup) -> tuple[list, list]:
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