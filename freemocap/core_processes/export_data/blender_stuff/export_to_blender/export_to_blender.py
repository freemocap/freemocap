import logging
from pathlib import Path
from typing import Union

from freemocap.core_processes.export_data.blender_stuff.export_to_blender.methods.ajc_addon.run_ajc_addon_main import (
    run_ajc_blender_addon_subprocess,
)
from freemocap.core_processes.export_data.blender_stuff.get_best_guess_of_blender_path import (
    get_best_guess_of_blender_path,
)

logger = logging.getLogger(__name__)


def export_to_blender(
    recording_folder_path: Union[str, Path],
    blender_file_path: Union[str, Path],
    blender_exe_path: Union[str, Path],
    method: str = "ajc27_blender_addon",
):
    logger.info(
        f"Exporting session data to a Blender scene at: {str(blender_file_path)} using Blender executable at {str(blender_exe_path)}"
    )

    if method == "ajc27_blender_addon":
        run_ajc_blender_addon_subprocess(
            recording_folder_path=recording_folder_path,
            blender_file_path=blender_file_path,
            blender_exe_path=blender_exe_path,
        )

    logger.info("Done with Blender Export :D")


if __name__ == "__main__":
    recording_path = r"D:\Dropbox\FreeMoCapProject\FreeMocap_Data\old\sesh_2022-09-19_16_16_50_in_class_jsm"
    export_to_blender(recording_path, recording_path, get_best_guess_of_blender_path())
