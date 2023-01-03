import logging
import time
from pathlib import Path

import toml

import freemocap

logger = logging.getLogger(__name__)

# directory names
BASE_FREEMOCAP_DATA_FOLDER_NAME = "freemocap_data"
MOTION_CAPTURE_SESSIONS_FOLDER_NAME = "motion_capture_sessions"
CALIBRATIONS_FOLDER_NAME = "calibrations"
LOGS_INFO_AND_SETTINGS_FOLDER_NAME = "logs_info_and_settings"
LOG_FILE_FOLDER_NAME = "logs"

# file names
MOST_RECENT_RECORDING_TOML_FILENAME = "most_recent_recording.toml"
LAST_SUCCESSFUL_CALIBRATION_TOML_FILENAME = "last_successful_calibration.toml"

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


def get_motion_capture_session_folder_path(create_folder: bool = True):
    motion_capture_session_folder_path = (
        Path(get_freemocap_data_folder_path()) / MOTION_CAPTURE_SESSIONS_FOLDER_NAME
    )

    if create_folder:
        motion_capture_session_folder_path.mkdir(exist_ok=create_folder, parents=True)

    return str(motion_capture_session_folder_path)


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


def get_most_recent_recording_path() -> str:
    session_id_dict = toml.load(str(get_most_recent_recording_toml_path()))
    return session_id_dict["most_recent_recording_path"]


def get_last_successful_calibration_toml_path():
    return str(
        Path(get_logs_info_and_settings_folder_path())
        / LAST_SUCCESSFUL_CALIBRATION_TOML_FILENAME
    )
