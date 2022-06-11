import time
from pathlib import Path

BASE_FOLDER_NAME = "freemocap_data"


def create_session_id(string_tag: str = None):
    session_id = 'session_' + time.strftime("%m-%d-%Y-%H_%M_%S")
    if string_tag is None:
        return session_id
    else:
        return session_id + '_' + string_tag


def os_independent_home_dir():
    return str(Path.home())


def get_freemocap_data_folder_path():
    freemocap_data_folder_path = Path(os_independent_home_dir(), BASE_FOLDER_NAME)
    freemocap_data_folder_path.mkdir(exist_ok=True,parents=True)
    return str(freemocap_data_folder_path)


def get_session_folder_path(session_id: str):
    base_save_path = Path(get_freemocap_data_folder_path())
    session_path = base_save_path / session_id
    session_path.mkdir(exist_ok=True, parents=True)
    return str(session_path)


def get_synchronized_videos_folder_path(session_id: str):
    synchronized_videos_path = Path(get_session_folder_path(session_id)) / 'synchronized_videos'
    synchronized_videos_path.mkdir(exist_ok=True, parents=True)
    return str(synchronized_videos_path)


def get_calibration_videos_folder_path(session_id: str):
    calibration_videos_path = Path(get_session_folder_path(session_id)) / 'calibration_videos'
    calibration_videos_path.mkdir(exist_ok=True, parents=True)
    return str(calibration_videos_path)


def get_mediapipe_annotated_videos_folder_path(session_id: str):
    mediapipe_annotated_videos_path = Path(get_session_folder_path(session_id)) / 'mediapipe_annotated_videos'
    mediapipe_annotated_videos_path.mkdir(exist_ok=True, parents=True)
    return str(mediapipe_annotated_videos_path)


def get_output_data_folder_path(session_id: str):
    output_data_folder_path = Path(get_session_folder_path(session_id)) / 'output_data_files'
    output_data_folder_path.mkdir(exist_ok=True, parents=True)
    return str(output_data_folder_path)
