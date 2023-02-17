import logging
from pathlib import Path
from typing import Union

from freemocap.core_processes.visualization.blender_stuff.create_blend_file_from_session_data import (
    create_blend_file_from_session_data_megascript_take1,
    create_blend_file_from_session_data_cgtinker,
)
from freemocap.core_processes.visualization.blender_stuff.get_best_guess_of_blender_path import (
    get_best_guess_of_blender_path,
)

logger = logging.getLogger(__name__)


def export_to_blender(
    recording_folder_path: Union[str, Path],
    blender_file_path: Union[str, Path],
    blender_exe_path: Union[str, Path] = get_best_guess_of_blender_path(),
    method: str = "cgtinker",
):

    logger.info(
        f"Exporting session data to a Blender scene at: {str(blender_file_path)} using Blender executable at {str(blender_exe_path)}"
    )

    if method == "megascript_take2":
        create_blend_file_from_session_data_megascript_take2(
            recording_folder_path=recording_folder_path,
            blender_file_path=blender_file_path,
            blender_exe_path=blender_exe_path,
        )
    elif method == "megascript_take1":
        create_blend_file_from_session_data_megascript_take1(
            recording_folder_path=recording_folder_path,
            blender_file_path=blender_file_path,
            blender_exe_path=blender_exe_path,
        )
    elif method == "cgtinker":
        create_blend_file_from_session_data_cgtinker(
            recording_folder_path=recording_folder_path,
            blender_file_path=blender_file_path,
            blender_exe_path=blender_exe_path,
        )

    return str(blender_file_path)


if __name__ == "__main__":

    recording_path = r"D:\Dropbox\FreeMoCapProject\FreeMocap_Data\old\sesh_2022-09-19_16_16_50_in_class_jsm"
    export_to_blender(recording_path, recording_path)
