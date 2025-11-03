import filecmp
import logging
import shutil
from pathlib import Path
from typing import Union

from freemocap.system.paths_and_filenames.path_getters import get_last_successful_calibration_toml_path

from freemocap.zzold.core_processes.capture_volume_calibration.anipose_camera_calibration.run_anipose_calibration_algorithm import \
    AniposeCameraGroup

logger = logging.getLogger(__name__)


def load_most_recent_anipose_calibration_toml(
    save_copy_of_calibration_to_this_path: Union[str, Path, None] = None
) -> AniposeCameraGroup:
    most_recent_calibration_toml_path = get_last_successful_calibration_toml_path()
    logger.info(f"loading `most recent calibration from:{str(most_recent_calibration_toml_path)}")
    if save_copy_of_calibration_to_this_path is not None:
        logger.info(f"Saving copy of `most_recent_calibration.toml` to {save_copy_of_calibration_to_this_path}")

        shutil.copy(
            str(most_recent_calibration_toml_path),
            str(Path(save_copy_of_calibration_to_this_path) / Path(most_recent_calibration_toml_path).name),
        )

    try:
        camera_group = AniposeCameraGroup.load(str(most_recent_calibration_toml_path))
    except Exception as e:
        logger.exception(e)
        raise
    return camera_group


def load_anipose_calibration_toml_from_path(
    camera_calibration_data_toml_path: Union[str, Path],
    save_copy_of_calibration_to_this_path: Union[str, Path, None] = None,
) -> AniposeCameraGroup:
    logger.info(f"loading camera calibration file from:{str(camera_calibration_data_toml_path)}")
    try:
        anipose_calibration_object = AniposeCameraGroup.load(str(camera_calibration_data_toml_path))
        if save_copy_of_calibration_to_this_path is not None:
            copy_toml_path = str(
                Path(save_copy_of_calibration_to_this_path) / Path(camera_calibration_data_toml_path).name
            )

            if Path(copy_toml_path).is_file() and not filecmp.cmp(
                str(camera_calibration_data_toml_path), copy_toml_path
            ):
                logger.info(
                    f"Saving copy of {camera_calibration_data_toml_path} to {save_copy_of_calibration_to_this_path}"
                )
                shutil.copyfile(str(camera_calibration_data_toml_path), copy_toml_path)

        return anipose_calibration_object
    except Exception as e:
        logger.error(f"Failed to load anipose calibration info from {str(camera_calibration_data_toml_path)}")
        raise e


def load_calibration_from_session_id(
    session_calibration_file_path: Union[str, Path],
) -> AniposeCameraGroup:
    logger.info(f"loading camera calibration file from:{str(session_calibration_file_path)}")
    try:
        return AniposeCameraGroup.load(str(session_calibration_file_path))
    except Exception as e:
        logger.error(f"Failed to load anipose calibration info from {str(session_calibration_file_path)}")
        raise e
