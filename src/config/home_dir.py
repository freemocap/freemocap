import logging
import time
from pathlib import Path

import toml

logger = logging.getLogger(__name__)

BASE_FOLDER_NAME = "freemocap_data"
MOST_RECENT_SESSION_ID_FILENAME = "most_recent_session_id.toml"


def create_session_id(string_tag: str = None):
    session_id = "session_" + time.strftime("%m-%d-%Y-%H_%M_%S")

    if string_tag is not None:
        session_id = session_id + "_" + string_tag

    return session_id


def save_most_recent_session_id_to_a_toml_in_the_freemocap_data_folder(session_id: str):
    session_id_dict = {}
    session_id_dict["session_id"] = session_id

    output_file_name = MOST_RECENT_SESSION_ID_FILENAME
    output_file_path = Path(get_freemocap_data_folder_path()) / output_file_name
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
        Path(get_session_folder_path(session_id)) / "synchronized_videos"
    )
    if create_folder:
        synchronized_videos_path.mkdir(exist_ok=create_folder, parents=True)
        # this now counts as a "proper" session, so save it to the toml
        save_most_recent_session_id_to_a_toml_in_the_freemocap_data_folder(session_id)

    return str(synchronized_videos_path)


def get_calibration_videos_folder_path(session_id: str, create_folder: bool = True):
    calibration_videos_path = (
        Path(get_session_folder_path(session_id)) / "calibration_videos"
    )
    if create_folder:
        calibration_videos_path.mkdir(exist_ok=create_folder, parents=True)
    return str(calibration_videos_path)


def get_mediapipe_annotated_videos_folder_path(
    session_id: str, create_folder: bool = True
):
    mediapipe_annotated_videos_path = (
        Path(get_session_folder_path(session_id)) / "mediapipe_annotated_videos"
    )
    if create_folder:
        mediapipe_annotated_videos_path.mkdir(exist_ok=create_folder, parents=True)
    return str(mediapipe_annotated_videos_path)


def get_session_output_data_folder_path(session_id: str, create_folder: bool = True):
    output_data_folder_path = (
        Path(get_session_folder_path(session_id)) / "output_data_files"
    )
    if create_folder:
        output_data_folder_path.mkdir(exist_ok=create_folder, parents=True)
    return str(output_data_folder_path)


def get_session_calibration_file_path(session_id: str) -> str:
    calibration_file_name = f"{session_id}_camera_calibration.toml"
    calibration_file_path = (
        Path(get_session_folder_path(session_id)) / calibration_file_name
    )
    return str(calibration_file_path)
