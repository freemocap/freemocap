import logging
import time
from pathlib import Path

import toml

logger = logging.getLogger(__name__)

# directory names
BASE_FOLDER_NAME = "freemocap_data"
LOG_FILE_FOLDER_NAME = "logs"
SYNCHRONIZED_VIDEOS_FOLDER_NAME = "synchronized_videos"
CALIBRATION_VIDEOS_FOLDER_NAME = "calibration_videos"
ANNOTATED_VIDEOS_FOLDER_NAME = "annotated_videos"
OUTPUT_DATA_FOLDER_NAME = "output_data"
DIAGNOSTIC_PLOTS_FOLDER_NAME = "diagnostic_plots"

# file names
MOST_RECENT_SESSION_ID_FILENAME = "most_recent_session_id.toml"
CAMERA_CALIBRATION_FILE_NAME = "camera_calibration_data.toml"
MEDIAPIPE_2D_NPY_FILE_NAME = (
    "mediapipe_2dData_numCams_numFrames_numTrackedPoints_pixelXY.npy"
)
MEDIAPIPE_3D_NPY_FILE_NAME = (
    "mediapipe_3dData_numFrames_numTrackedPoints_spatialXYZ.npy"
)
MEDIAPIPE_REPROJECTION_ERROR_NPY_FILE_NAME = (
    "mediapipe_3dData_numFrames_numTrackedPoints_reprojectionError.npy"
)

SKELETON_BODY_CSV_FILE_NAME = "mediapipe_body_3d_xyz.csv"


def create_default_session_id(string_tag: str = None):
    session_id = "session_" + time.strftime("%m-%d-%Y-%H_%M_%S")

    if string_tag is not None:
        session_id = session_id + "_" + string_tag

    return session_id


def get_log_file_path():
    log_folder_path = Path(get_freemocap_data_folder_path()) / LOG_FILE_FOLDER_NAME
    log_folder_path.mkdir(exist_ok=True, parents=True)
    log_file_path = log_folder_path / create_log_file_name()
    return log_file_path


def create_log_file_name():
    return "log_" + time.strftime("%m-%d-%Y-%H_%M_%S") + ".log"


def save_most_recent_session_id_to_a_toml_in_the_freemocap_data_folder(session_id: str):
    session_id_dict = {}
    session_id_dict["session_id"] = session_id

    output_file_path = (
        Path(get_freemocap_data_folder_path()) / MOST_RECENT_SESSION_ID_FILENAME
    )
    with open(str(output_file_path), "w") as toml_file:
        toml.dump(session_id_dict, toml_file)


def get_most_recent_session_id() -> str:
    session_id_toml_path = (
        Path(get_freemocap_data_folder_path()) / MOST_RECENT_SESSION_ID_FILENAME
    )
    session_id_dict = toml.load(str(session_id_toml_path))
    return session_id_dict["session_id"]


def os_independent_home_dir():
    return str(Path.home())


def get_freemocap_data_folder_path(create_folder: bool = True):
    freemocap_data_folder_path = Path(os_independent_home_dir(), BASE_FOLDER_NAME)

    if create_folder:
        freemocap_data_folder_path.mkdir(exist_ok=create_folder, parents=True)

    return str(freemocap_data_folder_path)


def get_session_folder_path(session_id: str, create_folder: bool = False):
    base_save_path = Path(get_freemocap_data_folder_path())
    session_path = base_save_path / session_id
    if create_folder:
        session_path.mkdir(exist_ok=True, parents=True)
    return str(session_path)


def create_session_folder(session_id: str):
    session_path = Path(get_session_folder_path(session_id, create_folder=True))
    logger.info(f"Creating session folder at: {str(session_path)}")


def get_synchronized_videos_folder_path(session_id: str, create_folder: bool = True):
    synchronized_videos_path = (
        Path(get_session_folder_path(session_id)) / SYNCHRONIZED_VIDEOS_FOLDER_NAME
    )
    if create_folder:
        synchronized_videos_path.mkdir(exist_ok=create_folder, parents=True)
        # this now counts as a "proper" session, so save it to the toml
        save_most_recent_session_id_to_a_toml_in_the_freemocap_data_folder(session_id)

    return str(synchronized_videos_path)


def get_calibration_videos_folder_path(session_id: str, create_folder: bool = True):
    calibration_videos_path = (
        Path(get_session_folder_path(session_id)) / CALIBRATION_VIDEOS_FOLDER_NAME
    )
    if create_folder:
        calibration_videos_path.mkdir(exist_ok=create_folder, parents=True)
        # this now counts as a "proper" session, so save it to the toml
        save_most_recent_session_id_to_a_toml_in_the_freemocap_data_folder(session_id)
    return str(calibration_videos_path)


def get_annotated_videos_folder_path(session_id: str, create_folder: bool = False):
    annotated_videos_path = (
        Path(get_session_folder_path(session_id)) / ANNOTATED_VIDEOS_FOLDER_NAME
    )
    if create_folder:
        annotated_videos_path.mkdir(exist_ok=create_folder, parents=True)
    return str(annotated_videos_path)


def get_output_data_folder_path(session_id: str, create_folder: bool = True):
    output_data_folder_path = (
        Path(get_session_folder_path(session_id)) / OUTPUT_DATA_FOLDER_NAME
    )
    if create_folder:
        output_data_folder_path.mkdir(exist_ok=create_folder, parents=True)
    return str(output_data_folder_path)


def get_session_calibration_toml_file_path(session_id: str) -> str:
    calibration_file_path = (
        Path(get_session_folder_path(session_id)) / CAMERA_CALIBRATION_FILE_NAME
    )
    return str(calibration_file_path)


def get_skeleton_body_csv_path(session_id: str) -> str:
    skeleton_body_data_path = (
        Path(get_output_data_folder_path(session_id)) / SKELETON_BODY_CSV_FILE_NAME
    )
    return str(skeleton_body_data_path)


def get_blender_file_path(session_id: str) -> str:
    blend_file_name = session_id + ".blend"
    blender_file_path = Path(get_output_data_folder_path(session_id)) / blend_file_name
    return str(blender_file_path)
