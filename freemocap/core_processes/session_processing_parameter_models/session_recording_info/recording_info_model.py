from pathlib import Path
from typing import Union

from freemocap.configuration.paths_and_files_names import (
    get_last_successful_calibration_toml_path,
    OUTPUT_DATA_FOLDER_NAME,
    SYNCHRONIZED_VIDEOS_FOLDER_NAME,
)
from freemocap.core_processes.session_processing_parameter_models.session_recording_info.recording_folder_status_checker import (
    RecordingFolderStatusChecker,
)


class RecordingInfoModel:
    def __init__(
        self,
        recording_folder_path: Union[Path, str],
        calibration_toml_path: Union[Path, str] = None,
    ):
        self._path = Path(recording_folder_path)
        self._name = self._path.name

        self._output_data_folder_path = Path(self._path) / OUTPUT_DATA_FOLDER_NAME

        self._synchronized_videos_folder_path: Union[Path, str] = (
            Path(self._path) / SYNCHRONIZED_VIDEOS_FOLDER_NAME
        )

        if calibration_toml_path is None:
            self._calibration_toml_file_path = (
                get_last_successful_calibration_toml_path()
            )
        else:
            self._calibration_toml_file_path = calibration_toml_path

        self._recording_folder_status_checker = RecordingFolderStatusChecker(self._path)

    @property
    def path(self) -> str:
        return str(self._path)

    @property
    def name(self) -> str:
        return self._name

    @property
    def output_data_folder_path(self) -> str:
        return str(self._output_data_folder_path)

    @property
    def synchronized_videos_folder_path(self) -> str:
        return str(self._synchronized_videos_folder_path)

    @property
    def calibration_toml_file_path(self) -> str:
        return str(self._calibration_toml_file_path)

    @property
    def synchronized_videos_exist(self) -> bool:
        return self._recording_folder_status_checker.check_synchronized_videos_exist()

    @property
    def data2d_exists(self) -> bool:
        return self._recording_folder_status_checker.check_data2d_exists()

    @property
    def data3d_exists(self) -> bool:
        return self._recording_folder_status_checker.check_data3d_exists()

    @property
    def center_of_mass_data_exists(self) -> bool:
        return self._recording_folder_status_checker.check_center_of_mass_data_exists()

    def calibration_toml_file_exists(self) -> bool:
        return Path(self._calibration_toml_file_path).is_file()
