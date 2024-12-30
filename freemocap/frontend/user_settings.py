import json
from pathlib import Path

from pydantic import BaseModel

from freemocap.core_processes.export_data.blender_stuff.get_best_guess_of_blender_path import (
    get_best_guess_of_blender_path,
)
from freemocap.system.paths_and_filenames.file_and_folder_names import BASE_FREEMOCAP_DATA_FOLDER_NAME
from freemocap.system.paths_and_filenames.path_getters import get_user_settings_path


class UserSettings(BaseModel):
    send_user_pings: bool = True
    show_welcome_screen: bool = True
    auto_process_videos_on_save: bool = True
    generate_jupyter_notebook: bool = True
    auto_open_in_blender: bool = True
    charuco_square_size: float = 39
    annotate_charuco_images: bool = False
    freemocap_data_folder_path: str = str(Path(Path.home(), BASE_FREEMOCAP_DATA_FOLDER_NAME))
    blender_path: str = str(get_best_guess_of_blender_path())


    def save_user_settings(self) -> None:
        with open(get_user_settings_path(), "w") as file:
            json.dump(self.model_dump(mode="json"), file, indent=4)

    @classmethod
    def load_user_settings(cls):
        try:
            with open(get_user_settings_path(), "r") as file:
                return UserSettings(**json.load(file))
        except OSError:
            gui_state = UserSettings()
        return gui_state
