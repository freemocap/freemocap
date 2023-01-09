from pathlib import Path
from typing import Union

from freemocap.configuration.paths_and_files_names import (
    create_new_session_folder,
    get_most_recent_recording_path,
)
from freemocap.core_processes.session_processing_parameter_models.session_recording_info.recording_info_model import (
    RecordingInfoModel,
)


class SessionInfoModel:
    def __init__(
        self,
        use_most_recent: bool = False,
        session_folder_path: Union[str, Path] = None,
        recording_folder_path: Union[str, Path] = None,
        calibration_toml_path: Union[str, Path] = None,
    ):

        if session_folder_path is None:
            if use_most_recent:
                self._session_folder_path = Path(
                    get_most_recent_recording_path()
                ).parent
                recording_folder_path = get_most_recent_recording_path()
            else:
                self._session_folder_path = Path(create_new_session_folder())
                self._recording_folder_path = None

            self._session_name: str = Path(self._session_folder_path).stem

            if recording_folder_path is not None:
                self._recording_info_model = RecordingInfoModel(
                    recording_folder_path=recording_folder_path,
                    calibration_toml_path=calibration_toml_path,
                )

            else:
                self._recording_info_model = self.get_latest_internal_recording_info()

    @property
    def session_name(self):
        return self._session_name

    @property
    def session_folder_path(self) -> str:
        return str(self._session_folder_path)

    @property
    def recording_info_model(self) -> RecordingInfoModel:
        return self._recording_info_model

    def set_recording_info(
        self,
        recording_folder_path: Union[RecordingInfoModel, Union[Path, str]],
        calibration_toml_path: Union[Path, str] = None,
    ):
        if isinstance(recording_folder_path, RecordingInfoModel):
            self._recording_info_model = recording_folder_path
        else:
            self._recording_info_model = RecordingInfoModel(
                recording_folder_path=recording_folder_path,
                calibration_toml_path=calibration_toml_path,
            )

    def get_latest_internal_recording_info(self):
        recording_folders = [
            folder_path
            for folder_path in self._session_folder_path.iterdir()
            if folder_path.is_dir()
        ]
        if len(recording_folders) > 0:
            latest_recording_folder = sorted(recording_folders)[-1]
            return RecordingInfoModel(recording_folder_path=latest_recording_folder)
        else:
            return None
