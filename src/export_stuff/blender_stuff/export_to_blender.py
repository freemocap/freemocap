import os

from pathlib import Path
from typing import Union


from src.export_stuff.blender_stuff.create_blend_file_from_session_data import (
    create_blend_file_from_session_data,
)
import logging

logger = logging.getLogger(__name__)


def export_to_blender(
    session_folder_path: Union[str, Path], blender_exe_path: Union[str, Path]
):

    blender_file_name = Path(session_folder_path).stem + ".blend"
    blender_file_path = Path(session_folder_path) / blender_file_name
    logger.info(
        f"Exporting session data to a Blender scene at: {str(blender_file_path)}"
    )

    create_blend_file_from_session_data(
        session_folder_path=session_folder_path, blender_exe_path=blender_exe_path
    )

    return str(blender_file_path)


if __name__ == "__main__":
    from src.config.home_dir import get_most_recent_session_id

    export_to_blender(get_most_recent_session_id())
