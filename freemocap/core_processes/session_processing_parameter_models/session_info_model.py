from pathlib import Path
from typing import Union

from pydantic import BaseModel

from freemocap.configuration.paths_and_files_names import (
    get_last_successful_calibration_toml_path,
    get_most_recent_recording_path,
    logger,
    OUTPUT_DATA_FOLDER_NAME,
    SYNCHRONIZED_VIDEOS_FOLDER_NAME,
)


class SessionInfoModel:
    _session_folder_path: Union[Path, str] = str(
        Path(get_most_recent_recording_path()).parent
    )
    _recording_folder_path: Union[Path, str] = get_most_recent_recording_path()

    _session_name: str = Path(_session_folder_path).stem
    _recording_name: str = Path(_recording_folder_path).stem

    output_data_folder_path: Union[Path, str] = (
        Path(_recording_folder_path) / OUTPUT_DATA_FOLDER_NAME
    )

    synchronized_videos_folder_path: Union[Path, str] = (
        Path(_recording_folder_path) / SYNCHRONIZED_VIDEOS_FOLDER_NAME
    )

    calibration_toml_file_path: Union[
        Path, str
    ] = get_last_successful_calibration_toml_path()

    @property
    def session_name(self):
        return self._session_name

    @property
    def recording_name(self):
        return self._recording_name

    @property
    def session_folder_path(self) -> str:
        return str(self._session_folder_path)

    @session_folder_path.setter
    def session_folder_path(self, session_folder_path: Union[Path, str]):

        try:
            Path(
                session_folder_path
            ).is_dir(), f"Session folder path {session_folder_path} is not a directory"
        except Exception as e:
            logger.warning(f"Problem setting session folder path: {e}")

        if Path(session_folder_path) not in Path(self._recording_folder_path).parents:
            logger.warning(
                f"Session folder path {session_folder_path} is not a parent of recording folder path {self._recording_folder_path} - resetting recording folder path"
            )
            if len(list(Path(session_folder_path).iterdir())) > 0:
                self._recording_folder_path = list(Path(session_folder_path).iterdir())[
                    0
                ]
            else:
                self.recording_folder_path = None

        self._session_folder_path = str(session_folder_path)
        self._session_name = str(Path(self.session_folder_path).stem)

    @property
    def recording_folder_path(self) -> Path:
        return Path(self._recording_folder_path)

    @recording_folder_path.setter
    def recording_folder_path(
        self, recording_folder_path: Union[Path, str], update_subfolders: bool = True
    ):

        try:
            Path(
                recording_folder_path
            ).is_dir(), f"Recording folder path {recording_folder_path} is not a directory"
        except Exception as e:
            logger.warning(f"Problem setting recording folder path: {e}")
            return

        if not Path(recording_folder_path).parent == Path(self.session_folder_path):
            logger.warning(
                f"Recording folder path {recording_folder_path} is not a child of session folder path {self.session_folder_path} - resetting session folder path"
            )
            self._session_folder_path = Path(recording_folder_path).parent

        self._recording_folder_path = str(recording_folder_path)

        self._recording_name = str(self.recording_folder_path.stem)
        self._session_name = str(Path(self.session_folder_path).stem)

        if update_subfolders:
            self.update_subfolders(self._recording_folder_path)

    @property
    def synchronized_videos_recorded(self) -> bool:
        return False

    @property
    def tracking_2d_complete(self) -> bool:
        return False

    @property
    def reconstruct_3d_complete(self) -> bool:
        return False

    @property
    def post_processing_complete(self) -> bool:
        return False

    def update_subfolders(self, recording_folder_path: Union[Path, str] = None):
        if recording_folder_path is None:
            self.output_data_folder_path = "---"
            self.synchronized_videos_folder_path = "---"
            return

        self.output_data_folder_path = (
            Path(recording_folder_path) / OUTPUT_DATA_FOLDER_NAME
        )
        self.synchronized_videos_folder_path = (
            Path(recording_folder_path) / SYNCHRONIZED_VIDEOS_FOLDER_NAME
        )
