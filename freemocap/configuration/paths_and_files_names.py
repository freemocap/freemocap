import time
from pathlib import Path

import toml

import freemocap
import logging

logger = logging.getLogger(__name__)

# directory names
BASE_FREEMOCAP_DATA_FOLDER_NAME = "freemocap_data"
RECORDING_SESSIONS_FOLDER_NAME = "recording_sessions"
CALIBRATIONS_FOLDER_NAME = "calibrations"
LOGS_INFO_AND_SETTINGS_FOLDER_NAME = "logs_info_and_settings"
LOG_FILE_FOLDER_NAME = "logs"
OUTPUT_DATA_FOLDER_NAME = "output_data"
SYNCHRONIZED_VIDEOS_FOLDER_NAME = "synchronized_videos"
RAW_DATA_FOLDER_NAME = "raw_data"
CENTER_OF_MASS_FOLDER_NAME = "center_of_mass"

# file names
MOST_RECENT_RECORDING_TOML_FILENAME = "most_recent_recording.toml"
LAST_SUCCESSFUL_CALIBRATION_TOML_FILENAME = "last_successful_calibration.toml"
MEDIAPIPE_2D_NPY_FILE_NAME = (
    "mediapipe2dData_numCams_numFrames_numTrackedPoints_pixelXY.npy"
)
MEDIAPIPE_3D_NPY_FILE_NAME = "mediapipe3dData_numFrames_numTrackedPoints_spatialXYZ.npy"
MEDIAPIPE_REPROJECTION_ERROR_NPY_FILE_NAME = (
    "mediapipe3dData_numFrames_numTrackedPoints_reprojectionError.npy"
)
MEDIAPIPE_BODY_3D_DATAFRAME_CSV_FILE_NAME = "mediapipe_body_3d_xyz.csv"

SEGMENT_CENTER_OF_MASS_NPY_FILE_NAME = "segmentCOM_frame_joint_xyz.npy"

TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME = "total_body_center_of_mass_xyz.npy"


# logo
PATH_TO_FREEMOCAP_LOGO_SVG = str(
    Path(freemocap.__file__).parent.parent
    / "assets/logo/freemocap-logo-black-border.svg"
)


def os_independent_home_dir():
    return str(Path.home())


def get_log_file_path():
    log_folder_path = (
        Path(get_freemocap_data_folder_path())
        / LOGS_INFO_AND_SETTINGS_FOLDER_NAME
        / LOG_FILE_FOLDER_NAME
    )
    log_folder_path.mkdir(exist_ok=True, parents=True)
    log_file_path = log_folder_path / create_log_file_name()
    return str(log_file_path)


def create_log_file_name():
    return "log_" + time.strftime("%m-%d-%Y-%H_%M_%S") + ".log"


def get_freemocap_data_folder_path(create_folder: bool = True):
    freemocap_data_folder_path = Path(
        os_independent_home_dir(), BASE_FREEMOCAP_DATA_FOLDER_NAME
    )

    if create_folder:
        freemocap_data_folder_path.mkdir(exist_ok=create_folder, parents=True)

    return str(freemocap_data_folder_path)


def get_calibrations_folder_path(create_folder: bool = True):
    calibration_folder_path = (
        Path(get_freemocap_data_folder_path()) / CALIBRATIONS_FOLDER_NAME
    )

    if create_folder:
        calibration_folder_path.mkdir(exist_ok=create_folder, parents=True)

    return str(calibration_folder_path)


def default_session_name(string_tag: str = None):

    if string_tag is not None:
        string_tag = f"_{string_tag}"
    else:
        string_tag = ""

    session_name = time.strftime("session_%Y-%m-%d_%H_%M_%S" + string_tag)
    logger.debug(f"Creating default session name: {session_name}")

    return session_name


def create_new_session_folder():
    session_folder_path = (
        Path(get_recording_session_folder_path()) / default_session_name()
    )

    session_folder_path.mkdir(exist_ok=True, parents=True)
    return str(session_folder_path)


def get_recording_session_folder_path(create_folder: bool = True):
    recording_session_folder_path = (
        Path(get_freemocap_data_folder_path()) / RECORDING_SESSIONS_FOLDER_NAME
    )

    if create_folder:
        recording_session_folder_path.mkdir(exist_ok=create_folder, parents=True)

    return str(recording_session_folder_path)


def get_logs_info_and_settings_folder_path(create_folder: bool = True):
    logs_info_and_settings_folder_path = (
        Path(get_freemocap_data_folder_path()) / LOGS_INFO_AND_SETTINGS_FOLDER_NAME
    )

    if create_folder:
        logs_info_and_settings_folder_path.mkdir(exist_ok=create_folder, parents=True)

    return str(logs_info_and_settings_folder_path)


def get_css_stylesheet_path():
    return str(
        Path(__file__).parent.parent / "qt_gui" / "style_sheet" / "qt_style_sheet.css"
    )


def get_most_recent_recording_toml_path():
    return str(
        Path(get_logs_info_and_settings_folder_path())
        / MOST_RECENT_RECORDING_TOML_FILENAME
    )


def get_most_recent_recording_path(subfolder_str: str = None):

    if not Path(get_most_recent_recording_toml_path()).exists():
        logger.warning("`most_recent_recording.toml` does not exist. Returning None.")
        return None

    most_recent_recording_dict = toml.load(str(get_most_recent_recording_toml_path()))
    most_recent_recording_path = most_recent_recording_dict[
        "most_recent_recording_path"
    ]

    if subfolder_str is not None:

        try:
            # check if folder is specified in toml file, otherwise return default
            sub_folder_path = most_recent_recording_dict[subfolder_str]
        except KeyError:
            sub_folder_path = Path(most_recent_recording_path) / subfolder_str
        return str(sub_folder_path)

    else:

        return str(most_recent_recording_path)


def get_last_successful_calibration_toml_path():
    return str(
        Path(get_logs_info_and_settings_folder_path())
        / LAST_SUCCESSFUL_CALIBRATION_TOML_FILENAME
    )
