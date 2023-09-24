import logging
from pathlib import Path
from typing import Union, Dict

import numpy as np

from freemocap.system.paths_and_filenames.file_and_folder_names import (
    CENTER_OF_MASS_FOLDER_NAME,
    MEDIAPIPE_2D_NPY_FILE_NAME,
    RAW_MEDIAPIPE_3D_NPY_FILE_NAME,
    OUTPUT_DATA_FOLDER_NAME,
    RAW_DATA_FOLDER_NAME,
    TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME,
    MEDIAPIPE_REPROJECTION_ERROR_NPY_FILE_NAME,
    SYNCHRONIZED_VIDEOS_FOLDER_NAME,
    ANNOTATED_VIDEOS_FOLDER_NAME,
    MEDIAPIPE_3D_NPY_FILE_NAME,
)
from freemocap.system.paths_and_filenames.path_getters import create_camera_calibration_file_name, get_blender_file_path
from freemocap.tests.test_image_tracking_data_shape import test_image_tracking_data_shape
from freemocap.tests.test_mediapipe_skeleton_data_shape import test_mediapipe_skeleton_data_shape
from freemocap.tests.test_synchronized_video_frame_counts import test_synchronized_video_frame_counts
from freemocap.tests.test_total_body_center_of_mass_data_shape import test_total_body_center_of_mass_data_shape

logger = logging.getLogger(__name__)


class RecordingInfoModel:
    def __init__(
        self,
        recording_folder_path: Union[Path, str],
    ):
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

        self._recording_folder_status_checker = RecordingFolderStatusChecker(recording_info_model=self)

    @property
    def path(self) -> str:
        return str(self._path)

    @property
    def name(self) -> str:
        return self._name

    @property
    def status_check(self) -> Dict[str, bool]:
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
    def mediapipe_2d_data_npy_file_path(self):
        return str(Path(self._path) / OUTPUT_DATA_FOLDER_NAME / RAW_DATA_FOLDER_NAME / MEDIAPIPE_2D_NPY_FILE_NAME)

    @property
    def mediapipe_3d_data_npy_file_path(self):
        return str(Path(self._path) / OUTPUT_DATA_FOLDER_NAME / MEDIAPIPE_3D_NPY_FILE_NAME)

    @property
    def raw_mediapipe_3d_data_npy_file_path(self):
        return str(Path(self._path) / OUTPUT_DATA_FOLDER_NAME / RAW_DATA_FOLDER_NAME / RAW_MEDIAPIPE_3D_NPY_FILE_NAME)

    @property
    def mediapipe_reprojection_error_data_npy_file_path(self):
        return str(
            Path(self._path)
            / OUTPUT_DATA_FOLDER_NAME
            / RAW_DATA_FOLDER_NAME
            / MEDIAPIPE_REPROJECTION_ERROR_NPY_FILE_NAME
        )

    @property
    def total_body_center_of_mass_npy_file_path(self):
        return str(
            Path(self._path)
            / OUTPUT_DATA_FOLDER_NAME
            / CENTER_OF_MASS_FOLDER_NAME
            / TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME
        )

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
    def status_check(self) -> Dict[str, Union[bool, str, float]]:
        return {
            "synchronized_videos_status_check": self.check_synchronized_videos_status(),
            "data2d_status_check": self.check_data2d_status(),
            "data3d_status_check": self.check_data3d_status(),
            "center_of_mass_data_status_check": self.check_center_of_mass_data_status(),
            "blender_file_status_check": self.check_blender_file_status(),
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

    def check_data2d_status(self) -> bool:
        try:
            test_image_tracking_data_shape(
                synchronized_video_folder_path=self.recording_info_model.synchronized_videos_folder_path,
                image_tracking_data_file_path=self.recording_info_model.mediapipe_2d_data_npy_file_path,
            )

            return True
        except AssertionError:
            return False

    def check_data3d_status(self) -> bool:
        try:
            test_mediapipe_skeleton_data_shape(
                synchronized_video_folder_path=self.recording_info_model.synchronized_videos_folder_path,
                raw_skeleton_npy_file_path=self.recording_info_model.mediapipe_3d_data_npy_file_path,
                reprojection_error_file_path=self.recording_info_model.mediapipe_reprojection_error_data_npy_file_path,
            )
            return True
        except AssertionError:
            return False

    def check_center_of_mass_data_status(self) -> bool:
        try:
            test_total_body_center_of_mass_data_shape(
                synchronized_video_folder_path=self.recording_info_model.synchronized_videos_folder_path,
                total_body_center_of_mass_file_path=self.recording_info_model.total_body_center_of_mass_npy_file_path,
            )
            return True
        except AssertionError:
            return False

    def check_blender_file_status(self) -> bool:
        return Path(self.recording_info_model.blender_file_path).is_file()

    def check_calibration_toml_status(self) -> bool:
        toml_status = Path(self.recording_info_model.calibration_toml_path).is_file()
        if not toml_status:
            logger.info(
                "No calibration file found with session name, checking for other calibration files in recording session"
            )
            toml_status = self.check_for_calibration_toml_with_different_name()
        return toml_status

    def get_number_of_mp4s_in_synched_videos_directory(self) -> float:
        synchronized_directory_path = Path(self.recording_info_model.synchronized_videos_folder_path)
        video_count = 0.0

        if not synchronized_directory_path.exists():
            return video_count

        for file in synchronized_directory_path.iterdir():
            if file.is_file() and file.suffix.lower() == ".mp4":
                video_count += 1

        logger.info(f"Number of `.mp4`'s in {self.recording_info_model.synchronized_videos_folder_path}: {video_count}")
        return video_count

    def get_number_of_frames_in_videos(self):
        timestamps_directory_path = Path(self.recording_info_model.synchronized_videos_folder_path) / "timestamps"

        if not timestamps_directory_path.exists():
            return "No 'timestamps' directory found"

        if timestamps_directory_path.exists():
            frame_counts = {}

            for npy_file in timestamps_directory_path.iterdir():
                if npy_file.is_file() and npy_file.suffix.lower() == ".npy":
                    video_npy = np.load(str(npy_file))
                    frame_counts[npy_file.name] = str(len(video_npy) - 1)

            return frame_counts

    def check_for_calibration_toml_with_different_name(self) -> bool:
        for file in Path(self.recording_info_model.path).iterdir():
            if file.is_file() and file.name.endswith("camera_calibration.toml"):
                self.recording_info_model.calibration_toml_path = str(file)
                logger.info(f"Found calibration file at: {self.recording_info_model.calibration_toml_path}")
                return True
        return False
