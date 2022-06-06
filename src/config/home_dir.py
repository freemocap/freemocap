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
