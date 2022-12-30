import logging
import shutil
from pathlib import Path
from typing import Union

from src.config.home_dir import (
    CAMERA_CALIBRATION_FILE_NAME,
    get_freemocap_data_folder_path,
)
from src.core_processes.capture_volume_calibration.anipose_camera_calibration import (
    freemocap_anipose,
)

logger = logging.getLogger(__name__)


def load_most_recent_anipose_calibration_toml(
    save_copy_of_calibration_to_this_path: Union[str, Path] = None
):
    session_calibration_file_path = Path(
        get_freemocap_data_folder_path(), "last_successful_calibration.toml"
    )
    logger.info(
        f"loading `most recent calibration from:{str(session_calibration_file_path)}"
    )
    if save_copy_of_calibration_to_this_path is not None:
        logger.info(
            f"Saving copy of `most_recent_calibration.toml` to {save_copy_of_calibration_to_this_path}"
        )

        shutil.copy(
            str(session_calibration_file_path),
            str(
                Path(save_copy_of_calibration_to_this_path)
                / CAMERA_CALIBRATION_FILE_NAME
            ),
        )

    return freemocap_anipose.CameraGroup.load(str(session_calibration_file_path))


def load_anipose_calibration_toml_from_path(
    camera_calibration_data_toml_path: Union[str, Path],
    save_copy_of_calibration_to_this_path: Union[str, Path] = None,
):
    logger.info(
        f"loading camera calibration file from:{str(camera_calibration_data_toml_path)}"
    )
    try:
        anipose_calibration_object = freemocap_anipose.CameraGroup.load(
            str(camera_calibration_data_toml_path)
        )

        if save_copy_of_calibration_to_this_path is not None:
            logger.info(
                f"Saving copy of {camera_calibration_data_toml_path} to {save_copy_of_calibration_to_this_path}"
            )
            shutil.copy(
                str(camera_calibration_data_toml_path),
                str(
                    Path(save_copy_of_calibration_to_this_path)
                    / CAMERA_CALIBRATION_FILE_NAME
                ),
            )
        return anipose_calibration_object
    except Exception as e:
        logger.error(
            f"Failed to load anipose calibration info from {str(camera_calibration_data_toml_path)}"
        )
        raise e
        return None


def load_calibration_from_session_id(
    session_calibration_file_path: Union[str, Path],
):
    logger.info(
        f"loading camera calibration file from:{str(session_calibration_file_path)}"
    )
    try:

        return freemocap_anipose.CameraGroup.load(str(session_calibration_file_path))
    except Exception as e:
        logger.error(
            f"Failed to load anipose calibration info from {str(session_calibration_file_path)}"
        )
        raise e
