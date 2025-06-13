import json
from pathlib import Path

from pydantic import BaseModel

from freemocap.core_processes.export_data.blender_stuff.get_best_guess_of_blender_path import (
    get_best_guess_of_blender_path,
)
from freemocap.system.paths_and_filenames.file_and_folder_names import BASE_FREEMOCAP_DATA_FOLDER_NAME
from freemocap.core_processes.capture_volume_calibration.charuco_stuff.charuco_board_definition import CHARUCO_BOARDS


class GuiState(BaseModel):
    first_run: bool = False
    send_user_pings: bool = True
    show_welcome_screen: bool = True
    auto_process_videos_on_save: bool = True
    generate_jupyter_notebook: bool = True
    auto_open_in_blender: bool = True
    charuco_square_size: float = 39
    use_charuco_as_groundplane: bool = False
    annotate_charuco_images: bool = False
    freemocap_data_folder_path: str = str(Path(Path.home(), BASE_FREEMOCAP_DATA_FOLDER_NAME))
    blender_path: str = str(get_best_guess_of_blender_path())
    charuco_board_name: str = next(iter(CHARUCO_BOARDS))
    show_data_quality_warning: bool = False
    shown_latest_release_notes: bool = False



def save_gui_state(gui_state: GuiState, file_pathstring: str | None = None) -> None:
    from freemocap.system.paths_and_filenames.path_getters import get_gui_state_json_path

    if file_pathstring is None:
        file_pathstring = get_gui_state_json_path()
    with open(file_pathstring, "w") as file:
        json.dump(gui_state.model_dump(mode="json"), file, indent=4)


def load_gui_state(file_pathstring: str | None = None) -> GuiState:
    if file_pathstring is None:
        from freemocap.system.paths_and_filenames.path_getters import get_gui_state_json_path

        file_pathstring = get_gui_state_json_path()
    try:
        with open(file_pathstring, "r") as file:
            gui_state = GuiState(**json.load(file))
    except OSError:
        gui_state = GuiState(first_run=True)
    return gui_state
