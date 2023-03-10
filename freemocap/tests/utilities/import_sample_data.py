import io
import requests
import zipfile
from pathlib import Path

from freemocap.system.paths_and_files_names import (
    CENTER_OF_MASS_FOLDER_NAME,
    FIGSHARE_SAMPLE_DATA_FILE_NAME,
    FIGSHARE_ZIP_FILE_URL,
    MEDIAPIPE_IMAGE_NPY_FILE_NAME,
    MEDIAPIPE_RAW_SKELETON_NPY_FILE_NAME,
    MEDIAPIPE_REPROJECTION_ERROR_NPY_FILE_NAME,
    OUTPUT_DATA_FOLDER_NAME,
    RAW_DATA_FOLDER_NAME,
    SYNCHRONIZED_VIDEOS_FOLDER_NAME,
    TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME,
)


def load_sample_data() -> Path:
    extract_to_path = Path.home() / FIGSHARE_SAMPLE_DATA_FILE_NAME
    extract_to_path.mkdir(exist_ok=True)

    figshare_sample_data_path = extract_to_path / FIGSHARE_SAMPLE_DATA_FILE_NAME

    if not Path.exists(figshare_sample_data_path):
        r = requests.get(FIGSHARE_ZIP_FILE_URL)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extractall(extract_to_path)

    return figshare_sample_data_path


def find_data_folder_path(session_folder_path: Path) -> Path:
    for subfolder_path in session_folder_path.iterdir():

        if subfolder_path.name == OUTPUT_DATA_FOLDER_NAME:
            return subfolder_path

    raise Exception(f"Could not find a data folder in path {str(session_folder_path)}")


def find_synchronized_videos_folder_path(session_folder_path: Path) -> Path:
    for subfolder_path in session_folder_path.iterdir():

        if subfolder_path.name == SYNCHRONIZED_VIDEOS_FOLDER_NAME:
            return subfolder_path

    raise Exception(f"Could not find a videos folder in path {str(session_folder_path)}")


def find_skeleton_npy_file_name(data_folder_name: Path) -> Path:
    npy_path_list = [path.name for path in data_folder_name.glob("*.npy")]

    # TODO wait to change these file names until trent/singlecammy is merged
    if MEDIAPIPE_RAW_SKELETON_NPY_FILE_NAME in npy_path_list:
        return data_folder_name / MEDIAPIPE_RAW_SKELETON_NPY_FILE_NAME

    raise Exception(f"Could not find a skeleton NPY file in path {str(data_folder_name)}")


def find_total_body_center_of_mass_file_name(data_folder_name: Path) -> Path:
    npy_path_list = [path.name for path in data_folder_name.glob("*.npy")]

    center_of_mass_subfolder_path = data_folder_name / CENTER_OF_MASS_FOLDER_NAME
    if center_of_mass_subfolder_path.exists:
        center_of_mass_npy_path_list = [path.name for path in center_of_mass_subfolder_path.glob("*.npy")]

        if TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME in center_of_mass_npy_path_list:
            return center_of_mass_subfolder_path / TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME

    raise Exception(f"Could not find a total body center of mass npy file in path {str(data_folder_name)}")


def find_image_data_file_name(data_folder_name: Path) -> Path:
    npy_path_list = [path.name for path in data_folder_name.glob("*.npy")]

    raw_data_subfolder_path = data_folder_name / RAW_DATA_FOLDER_NAME
    if raw_data_subfolder_path.exists:
        raw_data_npy_path_list = [path.name for path in raw_data_subfolder_path.glob("*.npy")]

        if MEDIAPIPE_IMAGE_NPY_FILE_NAME in raw_data_npy_path_list:
            return raw_data_subfolder_path / MEDIAPIPE_IMAGE_NPY_FILE_NAME

    raise Exception(f"Could not find a 2d data file in path {str(data_folder_name)}")


def find_reprojection_error_file_name(data_folder_name: Path) -> Path:
    npy_path_list = [path.name for path in data_folder_name.glob("*.npy")]

    raw_data_subfolder_path = data_folder_name / RAW_DATA_FOLDER_NAME
    if raw_data_subfolder_path.exists:
        raw_data_npy_path_list = [path.name for path in raw_data_subfolder_path.glob("*.npy")]

        if MEDIAPIPE_REPROJECTION_ERROR_NPY_FILE_NAME in raw_data_npy_path_list:
            return raw_data_subfolder_path / MEDIAPIPE_REPROJECTION_ERROR_NPY_FILE_NAME

    raise Exception(f"Could not find reprojection error data file in path {str(data_folder_name)}")


if __name__ == "__main__":
    sample_data_path = load_sample_data()
