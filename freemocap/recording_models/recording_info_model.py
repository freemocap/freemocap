import logging
from pathlib import Path
from typing import Union, Dict

from freemocap.recording_models.recording_status_checker import RecordingFolderStatusChecker
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
    MEDIAPIPE_3D_NPY_FILE_NAME, )
from freemocap.system.paths_and_filenames.path_getters import create_camera_calibration_file_name, get_blender_file_path

logger = logging.getLogger(__name__)


class RecordingInfoModel:
    def __init__(
            self,
            recording_folder_path: Union[Path, str],
    ):
        if any([Path(recording_folder_path).name == SYNCHRONIZED_VIDEOS_FOLDER_NAME,
                Path(recording_folder_path).name == ANNOTATED_VIDEOS_FOLDER_NAME,
                Path(recording_folder_path).name == OUTPUT_DATA_FOLDER_NAME]):
            recording_folder_path = Path(recording_folder_path).parent

        self._path = Path(recording_folder_path)
        self._name = self._path.name

        self._calibration_toml_path = str(
            Path(self._path) / create_camera_calibration_file_name(recording_name=self._name))

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


