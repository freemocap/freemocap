import logging
from pathlib import Path
from typing import Union, Dict

import numpy as np

from freemocap.system.paths_and_filenames.file_and_folder_names import (
    CENTER_OF_MASS_FOLDER_NAME,
    DATA_2D_NPY_FILE_NAME,
    RAW_3D_NPY_FILE_NAME,
    OUTPUT_DATA_FOLDER_NAME,
    RAW_DATA_FOLDER_NAME,
    TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME,
    REPROJECTION_ERROR_NPY_FILE_NAME,
    SYNCHRONIZED_VIDEOS_FOLDER_NAME,
    ANNOTATED_VIDEOS_FOLDER_NAME,
    DATA_3D_NPY_FILE_NAME,
    OLD_DATA_2D_NPY_FILE_NAME,
    OLD_DATA_3D_NPY_FILE_NAME,
    OLD_RAW_3D_NPY_FILE_NAME,
    OLD_REPROJECTION_ERROR_NPY_FILE_NAME,
    OLD_TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME,
)
from freemocap.system.paths_and_filenames.path_getters import create_camera_calibration_file_name, get_blender_file_path
from freemocap.tests.test_image_tracking_data_shape import (
    test_image_tracking_data_exists,
    test_image_tracking_data_shape,
)
from freemocap.tests.test_skeleton_data_shape import test_skeleton_data_exists, test_skeleton_data_shape
from freemocap.tests.test_synchronized_video_frame_counts import test_synchronized_video_frame_counts
from freemocap.tests.test_total_body_center_of_mass_data_shape import (
    test_total_body_center_of_mass_data_exists,
    test_total_body_center_of_mass_data_shape,
)
from freemocap.utilities.get_number_of_frames_of_videos_in_a_folder import get_number_of_frames_of_videos_in_a_folder
from freemocap.utilities.get_video_paths import get_video_paths

logger = logging.getLogger(__name__)


class RecordingInfoModel:
    def __init__(self, recording_folder_path: Union[Path, str], active_tracker: str = "mediapipe"):
        if any(
            [
                Path(recording_folder_path).name == SYNCHRONIZED_VIDEOS_FOLDER_NAME,
                Path(recording_folder_path).name == ANNOTATED_VIDEOS_FOLDER_NAME,
                Path(recording_folder_path).name == OUTPUT_DATA_FOLDER_NAME,
            ]
        ):
            recording_folder_path = Path(recording_folder_path).parent

        self._path = Path(recording_folder_path)
        self._name = self._path.name

        self._calibration_toml_path = str(
            Path(self._path) / create_camera_calibration_file_name(recording_name=self._name)
        )

        self._active_tracker = active_tracker

        self._recording_folder_status_checker = RecordingFolderStatusChecker(recording_info_model=self)

    @property
    def active_tracker(self) -> str:
        return self._active_tracker

    @active_tracker.setter
    def active_tracker(self, tracker_name: str):
        self._active_tracker = tracker_name

    @property
    def file_prefix(self) -> str:
        if self.active_tracker != "" and self.active_tracker[-1] != "_":
            return self.active_tracker + "_"
        else:
            return self.active_tracker

    # TODO: Create setters for the path names that depend on tracker name, and an overall setter that sets them all at once
    @property
    def path(self) -> str:
        return str(self._path)

    @property
    def name(self) -> str:
        return self._name

    @property
    def status_check(self) -> Dict[str, Union[bool, str, float, dict]]:
        return self._recording_folder_status_checker.status_check

    @property
    def calibration_toml_path(self) -> str:
        return self._calibration_toml_path

    @calibration_toml_path.setter
    def calibration_toml_path(self, path: Union[Path, str]):
        self._calibration_toml_path = str(path)

    @property
    def output_data_folder_path(self) -> str:
        return str(Path(self._path) / OUTPUT_DATA_FOLDER_NAME)

    @property
    def raw_data_folder_path(self) -> str:
        return str(Path(self.output_data_folder_path) / RAW_DATA_FOLDER_NAME)

    @property
    def synchronized_videos_folder_path(self) -> str:
        return str(Path(self._path) / SYNCHRONIZED_VIDEOS_FOLDER_NAME)

    @property
    def annotated_videos_folder_path(self) -> str:
        return str(Path(self._path) / ANNOTATED_VIDEOS_FOLDER_NAME)

    @property
    def data_2d_npy_file_path(self):
        data_2d_path = Path(self.raw_data_folder_path) / (self.file_prefix + DATA_2D_NPY_FILE_NAME)
        old_data_2d_path = Path(self.raw_data_folder_path) / OLD_DATA_2D_NPY_FILE_NAME
        if self.active_tracker == "mediapipe" and old_data_2d_path.exists() and not data_2d_path.exists():
            return str(old_data_2d_path)
        else:
            return str(data_2d_path)

    @property
    def data_3d_npy_file_path(self):
        data_3d_path = Path(self._path) / OUTPUT_DATA_FOLDER_NAME / (self.file_prefix + DATA_3D_NPY_FILE_NAME)
        old_data_3d_path = Path(self._path) / OUTPUT_DATA_FOLDER_NAME / OLD_DATA_3D_NPY_FILE_NAME
        if self.active_tracker == "mediapipe" and old_data_3d_path.exists() and not data_3d_path.exists():
            return str(old_data_3d_path)
        else:
            return str(data_3d_path)

    @property
    def raw_data_3d_npy_file_path(self):
        raw_data_path = (
            Path(self._path)
            / OUTPUT_DATA_FOLDER_NAME
            / RAW_DATA_FOLDER_NAME
            / (self.file_prefix + RAW_3D_NPY_FILE_NAME)
        )
        old_raw_data_path = Path(self._path) / OUTPUT_DATA_FOLDER_NAME / RAW_DATA_FOLDER_NAME / OLD_RAW_3D_NPY_FILE_NAME
        if self.active_tracker == "mediapipe" and old_raw_data_path.exists() and not raw_data_path.exists():
            return str(old_raw_data_path)
        else:
            return str(raw_data_path)

    @property
    def reprojection_error_data_npy_file_path(self):
        reprojection_error_path = (
            Path(self._path)
            / OUTPUT_DATA_FOLDER_NAME
            / RAW_DATA_FOLDER_NAME
            / (self.file_prefix + REPROJECTION_ERROR_NPY_FILE_NAME)
        )
        raw_reprojection_error_path = (
            Path(self._path) / OUTPUT_DATA_FOLDER_NAME / RAW_DATA_FOLDER_NAME / OLD_REPROJECTION_ERROR_NPY_FILE_NAME
        )
        if (
            self.active_tracker == "mediapipe"
            and raw_reprojection_error_path.exists()
            and not reprojection_error_path.exists()
        ):
            return str(raw_reprojection_error_path)
        else:
            return str(reprojection_error_path)

    @property
    def total_body_center_of_mass_npy_file_path(self):
        total_body_com_path = (
            Path(self._path)
            / OUTPUT_DATA_FOLDER_NAME
            / CENTER_OF_MASS_FOLDER_NAME
            / (self.file_prefix + TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME)
        )
        raw_total_body_com_path = (
            Path(self._path)
            / OUTPUT_DATA_FOLDER_NAME
            / CENTER_OF_MASS_FOLDER_NAME
            / OLD_TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME
        )
        if self.active_tracker == "mediapipe" and raw_total_body_com_path.exists() and not total_body_com_path.exists():
            return str(raw_total_body_com_path)
        else:
            return str(total_body_com_path)

    @property
    def blender_file_path(self):
        return get_blender_file_path(str(self._path))

    @property
    def blender_file_status_check(self):
        return Path(self.blender_file_path).is_file()

    @property
    def calibration_toml_check(self) -> bool:
        return self._recording_folder_status_checker.check_calibration_toml_status()

    @property
    def synchronized_videos_status_check(self) -> bool:
        return self._recording_folder_status_checker.check_synchronized_videos_status()

    @property
    def single_video_check(self) -> bool:
        return self._recording_folder_status_checker.check_single_video()

    @property
    def data2d_status_check(self) -> bool:
        return self._recording_folder_status_checker.check_data2d_status()

    @property
    def data3d_status_check(self) -> bool:
        return self._recording_folder_status_checker.check_data3d_status()

    @property
    def center_of_mass_data_status_check(self) -> bool:
        return self._recording_folder_status_checker.check_center_of_mass_data_status()


class RecordingFolderStatusChecker:
    def __init__(self, recording_info_model: RecordingInfoModel):
        self.recording_info_model = recording_info_model

    @property
    def status_check(self) -> Dict[str, Union[bool, str, float, dict]]:
        return {
            "synchronized_videos_status_check": self.check_synchronized_videos_status(),
            "data2d_status_check": self.check_data2d_status(),
            "data3d_status_check": self.check_data3d_status(),
            "center_of_mass_data_status_check": self.check_center_of_mass_data_status(),
            "blender_file_status_check": self.check_blender_file_status(),
            "single_video_check": self.check_single_video(),
            "calibration_toml_check": self.check_calibration_toml_status(),
            "video_and_camera_info": {
                "number_of_synchronized_videos": self.get_number_of_mp4s_in_synched_videos_directory(),
                "number_of_frames_in_videos": self.get_number_of_frames_in_videos(),
                # 'camera_rotation_and_translation': self.get_camera_rotation_and_translation_from_calibration_toml()
            },
        }

    def check_synchronized_videos_status(self) -> bool:
        try:
            test_synchronized_video_frame_counts(self.recording_info_model.synchronized_videos_folder_path)
            return True
        except AssertionError:
            return False

    def check_single_video(self) -> bool:
        if len(get_video_paths(path_to_video_folder=self.recording_info_model.synchronized_videos_folder_path)) == 1:
            return True
        else:
            return False

    def check_data2d_status(self) -> bool:
        try:
            test_image_tracking_data_exists(
                synchronized_video_folder_path=self.recording_info_model.synchronized_videos_folder_path,
                image_tracking_data=self.recording_info_model.data_2d_npy_file_path,
            )
            test_image_tracking_data_shape(
                synchronized_video_folder_path=self.recording_info_model.synchronized_videos_folder_path,
                image_tracking_data=self.recording_info_model.data_2d_npy_file_path,
            )
            return True
        except AssertionError:
            return False

    def check_data3d_status(self) -> bool:
        try:
            test_skeleton_data_exists(
                raw_skeleton_data=self.recording_info_model.data_3d_npy_file_path,
                reprojection_error_data=self.recording_info_model.reprojection_error_data_npy_file_path,
            )
            test_skeleton_data_shape(
                synchronized_video_folder_path=self.recording_info_model.synchronized_videos_folder_path,
                raw_skeleton_data=self.recording_info_model.data_3d_npy_file_path,
                reprojection_error_data=self.recording_info_model.reprojection_error_data_npy_file_path,
            )
            return True
        except AssertionError:
            return False

    def check_center_of_mass_data_status(self) -> bool:
        try:
            test_total_body_center_of_mass_data_exists(
                total_body_center_of_mass_data=self.recording_info_model.total_body_center_of_mass_npy_file_path,
            )
            test_total_body_center_of_mass_data_shape(
                synchronized_video_folder_path=self.recording_info_model.synchronized_videos_folder_path,
                total_body_center_of_mass_data=self.recording_info_model.total_body_center_of_mass_npy_file_path,
            )
            return True
        except AssertionError:
            return False

    def check_blender_file_status(self) -> bool:
        return Path(self.recording_info_model.blender_file_path).is_file()

    def check_calibration_toml_status(self) -> bool:
        # TODO: check if adding a single video check here makes sense with the logic (i.e. will that ever give a misleading response)
        toml_status = Path(self.recording_info_model.calibration_toml_path).is_file()
        if not toml_status:
            logger.debug(
                "No calibration file found with session name, checking for other calibration files in recording session"
            )
            toml_status = self.check_for_calibration_toml_with_different_name()
        return toml_status

    def get_number_of_mp4s_in_synched_videos_directory(self) -> int:
        synchronized_directory_path = Path(self.recording_info_model.synchronized_videos_folder_path)

        if not synchronized_directory_path.exists():
            return 0

        video_count = len(get_video_paths(synchronized_directory_path))

        logger.info(f"Number of `.mp4`'s in {synchronized_directory_path}: {video_count}")
        return video_count

    def get_number_of_frames_in_videos(self) -> Dict[str, int]:
        timestamps_directory_path = Path(self.recording_info_model.synchronized_videos_folder_path) / "timestamps"

        if timestamps_directory_path.exists():
            frame_counts = {}

            for npy_file in timestamps_directory_path.iterdir():
                if npy_file.is_file() and npy_file.suffix.lower() == ".npy":
                    video_npy = np.load(str(npy_file))
                    frame_counts[npy_file.name] = len(video_npy) - 1
        else:
            logger.debug("No 'timestamps' directory, finding frame counts from synchronized videos")
            try:
                frame_counts = get_number_of_frames_of_videos_in_a_folder(
                    self.recording_info_model.synchronized_videos_folder_path
                )
            except ValueError:
                frame_counts = {}

        return frame_counts

    def check_for_calibration_toml_with_different_name(self) -> bool:
        try:
            for file in Path(self.recording_info_model.path).iterdir():
                if file.is_file() and file.name.endswith("camera_calibration.toml"):
                    self.recording_info_model.calibration_toml_path = str(file)
                    logger.info(f"Found calibration file at: {self.recording_info_model.calibration_toml_path}")
                    return True
        except Exception as e:
            logger.warning(f"Error checking for calibration toml with different name: {e}")
        return False
