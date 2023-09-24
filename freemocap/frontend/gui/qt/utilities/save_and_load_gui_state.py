import json
from pydantic import BaseModel


class GuiState(BaseModel):
    send_user_pings: bool = True
    show_welcome_screen: bool = True
    auto_process_videos_on_save: bool = True
    generate_jupyter_notebook: bool = True
    auto_open_in_blender: bool = True
    charuco_square_size: float = 39


def save_gui_state(gui_state: GuiState, file_pathstring: str = None):
    with open(file_pathstring, "w") as file:
        json.dump(gui_state.dict(), file, indent=4)


def load_gui_state(file_pathstring: str = None) -> GuiState:
    with open(file_pathstring, "r") as file:
        gui_state = GuiState(**json.load(file))
    return gui_state
