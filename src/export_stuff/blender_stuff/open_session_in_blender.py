import os
import sys
from pathlib import Path
import subprocess
from src.config.home_dir import get_session_folder_path, get_most_recent_session_id
from src.export_stuff.blender_stuff.create_blend_file_from_session_data import (
    create_blend_file_from_session_data,
)


def open_session_in_blender(session_id: str):
    create_blend_file_from_session_data(session_id)
    blender_file_name = session_id + ".blend"
    blender_file_path = Path(get_session_folder_path(session_id)) / blender_file_name
    os.startfile(str(blender_file_path))


if __name__ == "__main__":
    open_session_in_blender(get_most_recent_session_id())
