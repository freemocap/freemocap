from pathlib import Path
from typing import Union

from freemocap.configuration.paths_and_files_names import (
    CENTER_OF_MASS_FOLDER_NAME,
    logger,
    MEDIAPIPE_2D_NPY_FILE_NAME,
    MEDIAPIPE_3D_NPY_FILE_NAME,
    OUTPUT_DATA_FOLDER_NAME,
    RAW_DATA_FOLDER_NAME,
    SYNCHRONIZED_VIDEOS_FOLDER_NAME,
    TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME,
)


class RecordingFolderStatusChecker:
    def __init__(self, recording_path: Union[str, Path]):
        self.recording_path = Path(recording_path)

    def check_synchronized_videos_exist(self) -> bool:
        number_of_mp4_videos = len(
            list((self.recording_path / SYNCHRONIZED_VIDEOS_FOLDER_NAME).glob("*.mp4"))
        )
        logger.info(
            f"Found {number_of_mp4_videos} synchronized videos in {self.recording_path}"
        )
        return number_of_mp4_videos > 0

    def check_data2d_exists(self) -> bool:
        result = (
            self.recording_path
            / OUTPUT_DATA_FOLDER_NAME
            / RAW_DATA_FOLDER_NAME
            / MEDIAPIPE_2D_NPY_FILE_NAME
        ).is_file()
        logger.info(
            f"{MEDIAPIPE_2D_NPY_FILE_NAME} data exists in {self.recording_path}? {result}"
        )
        return result

    def check_data3d_exists(self) -> bool:
        result = (
            self.recording_path
            / OUTPUT_DATA_FOLDER_NAME
            / RAW_DATA_FOLDER_NAME
            / MEDIAPIPE_3D_NPY_FILE_NAME
        ).is_file()
        logger.info(
            f"{MEDIAPIPE_3D_NPY_FILE_NAME} data exists in {self.recording_path}? {result}"
        )
        return result

    def check_center_of_mass_data_exists(self) -> bool:
        result = (
            self.recording_path
            / OUTPUT_DATA_FOLDER_NAME
            / CENTER_OF_MASS_FOLDER_NAME
            / TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME
        ).is_file()
        logger.info(
            f"{TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME} data exists in {self.recording_path}? {result}"
        )
        return result
