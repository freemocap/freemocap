import time
from pathlib import Path

BASE_FOLDER_NAME = "freemocap_data"


def os_independent_home_dir():
    return str(Path.home())

def get_freemocap_data_folder_path():
    return str(Path(os_independent_home_dir(), BASE_FOLDER_NAME))

def create_session_id(string_tag: str = None):
    session_id = 'session_' + time.strftime("%m-%d-%Y-%H_%M_%S")
    if string_tag is None:
        return session_id
    else:
        return session_id + '_' + string_tag


def get_session_path(session_id: str):
    base_save_path = Path(get_freemocap_data_folder_path())
    session_path = base_save_path / session_id
    return str(session_path)

def get_synchronized_videos_path(session_id: str):
    synchronized_videos_path = Path(get_session_path(session_id)) / 'synchronized_videos'
    return str(synchronized_videos_path)

def get_calibration_videos_path(session_id: str):
    calibration_videos_path = Path(get_session_path(session_id)) / 'calibration_videos'
    return str(calibration_videos_path)

def get_mediapipe_annotated_videos_path(session_id: str):
    mediapipe_annotated_videos_path = Path(get_session_path(session_id)) / 'mediapipe_annotated_videos'
    return str(mediapipe_annotated_videos_path)
