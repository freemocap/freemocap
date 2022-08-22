import logging
from pathlib import Path
from typing import Union

from src.config.home_dir import get_freemocap_data_folder_path
from src.pipelines.calibration_pipeline.anipose_camera_calibration import (
    freemocap_anipose,
)

logger = logging.getLogger(__name__)


def load_most_recent_anipose_calibration_toml():
    last_successful_calibration_path = Path(
        get_freemocap_data_folder_path(), "last_successful_calibration.toml"
    )
    logger.info(
        f"loading `most recent calibration from:{str(last_successful_calibration_path)}"
    )
    return freemocap_anipose.CameraGroup.load(str(last_successful_calibration_path))


def load_calibration_from_session_id(session_calibration_file_path: Union[str, Path]):

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
