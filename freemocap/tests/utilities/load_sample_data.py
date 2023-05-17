import io
import logging

import requests
import zipfile
from pathlib import Path

from freemocap.system.paths_and_files_names import (
    CENTER_OF_MASS_FOLDER_NAME,
    FIGSHARE_SAMPLE_DATA_FILE_NAME,
    FIGSHARE_ZIP_FILE_URL,
    MEDIAPIPE_2D_NPY_FILE_NAME,
    RAW_MEDIAPIPE_3D_NPY_FILE_NAME,
    MEDIAPIPE_REPROJECTION_ERROR_NPY_FILE_NAME,
    OUTPUT_DATA_FOLDER_NAME,
    RAW_DATA_FOLDER_NAME,
    SYNCHRONIZED_VIDEOS_FOLDER_NAME,
    TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME, get_recording_session_folder_path,
)

logger = logging.getLogger(__name__)

# TODO - some of the naming in this file is inconsistent with the rest of the codebase. Needs fixed at some point. Also I think a lot of the `find_..` functions should be in a different file?


def load_sample_data(sample_data_zip_file_url: str = FIGSHARE_ZIP_FILE_URL) -> str:
    try:
        logger.info(f"Downloading sample data from {sample_data_zip_file_url}...")

        recording_session_folder_path = Path(get_recording_session_folder_path())
        recording_session_folder_path.mkdir(parents=True, exist_ok=True)

        r = requests.get(FIGSHARE_ZIP_FILE_URL, stream=True)
        r.raise_for_status()  # Check if request was successful

        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extractall(recording_session_folder_path)

        figshare_sample_data_path = recording_session_folder_path / FIGSHARE_SAMPLE_DATA_FILE_NAME
        logger.info(f"Sample data extracted to {str(figshare_sample_data_path)}")
        return str(figshare_sample_data_path)

    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
    except zipfile.BadZipFile as e:
        logger.error(f"Failed to unzip the file: {e}")


def find_output_data_folder_path(recording_folder_path: Path) -> Path:
    for subfolder_path in recording_folder_path.iterdir():
        if subfolder_path.name == OUTPUT_DATA_FOLDER_NAME:
            return subfolder_path

    raise Exception(f"Could not find a data folder in path {str(recording_folder_path)}")


def find_synchronized_videos_folder_path(recording_folder_path: Path) -> Path:
    for subfolder_path in recording_folder_path.iterdir():
        if subfolder_path.name == SYNCHRONIZED_VIDEOS_FOLDER_NAME:
            return subfolder_path

    raise Exception(f"Could not find a videos folder in path {str(recording_folder_path)}")


def find_raw_skeleton_npy_file_name(data_folder_name: Path) -> Path:
    raw_data_subfolder_path = data_folder_name / RAW_DATA_FOLDER_NAME
    if raw_data_subfolder_path.exists:
        raw_data_npy_path_list = [path.name for path in raw_data_subfolder_path.glob("*.npy")]
        if RAW_MEDIAPIPE_3D_NPY_FILE_NAME in raw_data_npy_path_list:
            return raw_data_subfolder_path / RAW_MEDIAPIPE_3D_NPY_FILE_NAME

    raise Exception(f"Could not find a skeleton NPY file in path {str(data_folder_name)}")


def find_total_body_center_of_mass_file_name(data_folder_name: Path) -> Path:
    center_of_mass_subfolder_path = data_folder_name / CENTER_OF_MASS_FOLDER_NAME
    if center_of_mass_subfolder_path.exists:
        center_of_mass_npy_path_list = [path.name for path in center_of_mass_subfolder_path.glob("*.npy")]

        if TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME in center_of_mass_npy_path_list:
            return center_of_mass_subfolder_path / TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME

    raise Exception(f"Could not find a total body center of mass npy file in path {str(data_folder_name)}")


def find_image_tracking_data_file_name(data_folder_name: Path) -> Path:
    raw_data_subfolder_path = data_folder_name / RAW_DATA_FOLDER_NAME
    if raw_data_subfolder_path.exists:
        raw_data_npy_path_list = [path.name for path in raw_data_subfolder_path.glob("*.npy")]

        if MEDIAPIPE_2D_NPY_FILE_NAME in raw_data_npy_path_list:
            return raw_data_subfolder_path / MEDIAPIPE_2D_NPY_FILE_NAME

    raise Exception(f"Could not find a 2d data file in path {str(data_folder_name)}")


def find_reprojection_error_file_name(data_folder_name: Path) -> Path:
    raw_data_subfolder_path = data_folder_name / RAW_DATA_FOLDER_NAME
    if raw_data_subfolder_path.exists:
        raw_data_npy_path_list = [path.name for path in raw_data_subfolder_path.glob("*.npy")]

        if MEDIAPIPE_REPROJECTION_ERROR_NPY_FILE_NAME in raw_data_npy_path_list:
            return raw_data_subfolder_path / MEDIAPIPE_REPROJECTION_ERROR_NPY_FILE_NAME

    raise Exception(f"Could not find reprojection error data file in path {str(data_folder_name)}")


if __name__ == "__main__":
    sample_data_path = load_sample_data()
    print(f"Sample data downloaded successfully to path: {str(sample_data_path)}")
