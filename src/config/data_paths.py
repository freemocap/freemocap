import os
from pathlib import Path

BASE_FOLDER_NAME = "freemocap_data"

freemocap_data_path = Path().joinpath(Path.home(), BASE_FOLDER_NAME)


def create_home_data_directory():
    path_as_str = str(freemocap_data_path)
    if not os.path.exists(path_as_str):
        os.makedirs(path_as_str)
