import logging
from pathlib import Path
from typing import Callable, Union

import numpy as np
import cv2

from freemocap.core_processes.capture_volume_calibration.anipose_camera_calibration import (
    freemocap_anipose,
)
from freemocap.core_processes.capture_volume_calibration.charuco_stuff.charuco_board_definition import (
    CharucoBoardDefinition,
)
from freemocap.system.paths_and_filenames.path_getters import (
    create_camera_calibration_file_name,
    get_calibrations_folder_path,
    get_last_successful_calibration_toml_path,
)
from freemocap.utilities.get_video_paths import get_video_paths

logger = logging.getLogger(__name__)


class AniposeCameraCalibrator:
    def __init__(
        self,
        charuco_board_object: CharucoBoardDefinition,
        charuco_square_size: Union[int, float],
        calibration_videos_folder_path: Union[str, Path],
        progress_callback: Callable[[str], None] = None,
    ):
        self._charuco_board_object = charuco_board_object
        self._progress_callback = progress_callback

        if charuco_square_size == 1:
            warning_string = "Charuco square size is not set, so units of 3d reconstructed data will be in units of `however_long_the_black_edge_of_the_charuco_square_was`. Please input `charuco_square_size` in millimeters (or your preferred unity of length)"
            logger.warning(warning_string)
            self._progress_callback(warning_string)
        self._charuco_square_size = charuco_square_size
        self._calibration_videos_folder_path = Path(calibration_videos_folder_path)
        self._recording_folder_path = Path(self._calibration_videos_folder_path).parent
        self._get_video_paths()
        self._initialize_anipose_objects()

    def _get_video_paths(
        self,
    ):
        self._list_of_video_paths = get_video_paths(path_to_video_folder=Path(self._calibration_videos_folder_path))

    def _initialize_anipose_objects(self):
        list_of_camera_names = [this_video_path.stem for this_video_path in self._list_of_video_paths]
        self._anipose_camera_group_object = freemocap_anipose.CameraGroup.from_names(list_of_camera_names)

        # add metadata
        self._anipose_camera_group_object.metadata["charuco_square_size"] = self._charuco_square_size
        self._anipose_camera_group_object.metadata["charuco_board_object"] = str(self._charuco_board_object)
        self._anipose_camera_group_object.metadata["path_to_recorded_videos"] = str(
            self._calibration_videos_folder_path
        )
        self._anipose_camera_group_object.metadata["date_time_calibrated"] = str(np.datetime64("now"))

        self._anipose_charuco_board = freemocap_anipose.AniposeCharucoBoard(
            self._charuco_board_object.number_of_squares_width,
            self._charuco_board_object.number_of_squares_height,
            square_length=self._charuco_square_size,  # mm
            marker_length=self._charuco_square_size * 0.8,
            marker_bits=4,
            dict_size=250,
        )

    def calibrate_camera_capture_volume(self, pin_camera_0_to_origin: bool = False) -> Path:
        video_paths_list_of_list_of_strings = [[str(this_path)] for this_path in self._list_of_video_paths]

        (
            error,
            charuco_frame_data,
            charuco_frame_numbers,
        ) = self._anipose_camera_group_object.calibrate_videos(
            video_paths_list_of_list_of_strings, self._anipose_charuco_board
        )
        success_str = "Anipose Calibration Successful!"
        logger.info(success_str)
        self._progress_callback(success_str)
        if pin_camera_0_to_origin:
            self._anipose_camera_group_object = self.pin_camera_zero_to_origin(cam_group=self._anipose_camera_group_object)
        # save calibration info to files
        calibration_toml_filename = create_camera_calibration_file_name(
            recording_name=self._calibration_videos_folder_path.parent.stem
        )

        calibration_folder_toml_path = Path(get_calibrations_folder_path()) / calibration_toml_filename

        self._anipose_camera_group_object.dump(calibration_folder_toml_path)
        logger.debug(
            f"anipose camera calibration data saved to Calibrations folder - {str(calibration_folder_toml_path)}"
        )

        recording_folder_toml_path = Path(self._recording_folder_path) / calibration_toml_filename

        self._anipose_camera_group_object.dump(recording_folder_toml_path)
        logger.debug(f"anipose camera calibration data saved to Recording folder - {str(recording_folder_toml_path)}")

        last_successful_calibration_toml_path = get_last_successful_calibration_toml_path()
        self._anipose_camera_group_object.dump(last_successful_calibration_toml_path)

        logger.debug(
            f"anipose camera calibration data also saved to 'Last Successful Calibration' - {last_successful_calibration_toml_path}"
        )
        self._progress_callback(
            "Anipose camera calibration data saved to calibrations folder, recording folder, and `Last Successful Calibration` file"
        )

        return calibration_folder_toml_path

    def pin_camera_zero_to_origin(self, cam_group: freemocap_anipose.CameraGroup):
        """
        Re-express all camera extrinsics relative to camera 0.

        This function performs two operations:
            1. Rotates all camera coordinate systems so that camera 0's orientation becomes the new world frame.
            2. Shifts the world origin to camera 0's position, making it the new coordinate origin (0, 0, 0).

        The result is that:
            - Camera 0 ends up with an identity rotation and zero translation.
            - All other cameras are expressed relative to camera 0's original position and orientation.

        Args:
            cam_group (freemocap_anipose.CameraGroup): A group of calibrated cameras whose extrinsics will be adjusted in place.
        """

        rvecs_new = self.align_rotations_to_cam0(cam_group=cam_group)
        cam_group.set_rotations(rvecs_new)
        tvecs_new = self.shift_origin_to_cam0(cam_group=cam_group)
        cam_group.set_translations(tvecs_new)
        return cam_group

    def align_rotations_to_cam0(self, cam_group:freemocap_anipose.CameraGroup):
        rvecs = cam_group.get_rotations()
        #get rotation of cam 0 to world
        R0,_  = cv2.Rodrigues(rvecs[0]) 

        rvecs_new = np.empty_like(rvecs)
        #rotates each cameras coordinate system into the new world space
        #R0 maps world -> cam0, so R0.T (which is also the inverse) maps cam0 -> world
        #R0 * R0^-1 = identity matrix, so this makes R0 the origin
        # then we map every other camera into the new world space
        for i in range(rvecs.shape[0]):
            Ri,_ = cv2.Rodrigues(rvecs[i])
            Ri_new,_ = cv2.Rodrigues(Ri @ R0.T)
            rvecs_new[i] = Ri_new.flatten()
        return rvecs_new
    
    def shift_origin_to_cam0(self, cam_group:freemocap_anipose.CameraGroup):
        # Get original translation and rotation vectors
        tvecs = cam_group.get_translations()
        rvecs = cam_group.get_rotations()

        # Extract camera 0's rotation and translation
        camera_0_translation = tvecs[0, :]
        camera_0_rotation = rvecs[0, :]

        # Get 3x3 rotation matrix for world -> cam 0
        R0, _ = cv2.Rodrigues(camera_0_rotation)

        # Get the vector that moves the world origin to cam 0 in the world frame
        delta_to_origin_world = - R0.T @ camera_0_translation

        # Create new translation vectors array
        new_tvecs = np.zeros_like(tvecs)

        # Apply offset to each camera's translation vector
        for cam_i in range(tvecs.shape[0]):
            Ri, _ = cv2.Rodrigues(rvecs[cam_i, :])
            # Transform the world offset into this camera's coordinate frame
            delta_to_origin_camera_i = Ri @ delta_to_origin_world
            # Update the translation vector
            new_tvecs[cam_i, :] = tvecs[cam_i, :] + delta_to_origin_camera_i
        return new_tvecs
