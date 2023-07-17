import logging
from pathlib import Path
from typing import Union

from freemocap.data_layer.export_data.blender_stuff.call_blender_subprocess_methods import (
    call_blender_subprocess_megascript_take2,
    call_blender_subprocess_cgtinker,
    call_blender_subprocess_alpha_megascript,
)
from freemocap.data_layer.export_data.blender_stuff.get_best_guess_of_blender_path import (
    get_best_guess_of_blender_path,
)

logger = logging.getLogger(__name__)


def export_to_blender(
    recording_folder_path: Union[str, Path],
    blender_file_path: Union[str, Path],
    blender_exe_path: Union[str, Path],
    method: str = "megascript_take2",
):
    logger.info(
        f"Exporting session data to a Blender scene at: {str(blender_file_path)} using Blender executable at {str(blender_exe_path)}"
    )

    if method == "megascript_take2":
        call_blender_subprocess_megascript_take2(
            recording_folder_path=recording_folder_path,
            blender_file_path=blender_file_path,
            blender_exe_path=blender_exe_path,
        )
    elif method == "alpha_megascript":
        call_blender_subprocess_alpha_megascript(
            recording_folder_path=recording_folder_path,
            blender_file_path=blender_file_path,
            blender_exe_path=blender_exe_path,
        )
    elif method == "cgtinker":
        call_blender_subprocess_cgtinker(
            recording_folder_path=recording_folder_path,
            blender_file_path=blender_file_path,
            blender_exe_path=blender_exe_path,
        )

    logger.info("blender subprocess finished")


if __name__ == "__main__":
    recording_path = r"D:\Dropbox\FreeMoCapProject\FreeMocap_Data\old\sesh_2022-09-19_16_16_50_in_class_jsm"
    export_to_blender(recording_path, recording_path, get_best_guess_of_blender_path())
