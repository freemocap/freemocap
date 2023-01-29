import logging
from pathlib import Path
from typing import Union

from freemocap.core_processes.visualization.blender_stuff.create_blend_file_from_session_data import (
    create_blend_file_from_session_data,
)
from freemocap.core_processes.visualization.blender_stuff.get_best_guess_of_blender_path import (
    get_best_guess_of_blender_path,
)

logger = logging.getLogger(__name__)


def export_to_blender(
    recording_folder_path: Union[str, Path],
    blender_file_path: Union[str, Path],
    blender_exe_path: Union[str, Path] = get_best_guess_of_blender_path(),
):

    logger.info(
        f"Exporting session data to a Blender scene at: {str(blender_file_path)} using Blender executable at {str(blender_exe_path)}"
    )

    create_blend_file_from_session_data(
        recording_folder_path=recording_folder_path,
        blender_file_path=blender_file_path,
        blender_exe_path=blender_exe_path,
    )

    return str(blender_file_path)


if __name__ == "__main__":
    from freemocap.configuration.paths_and_files_names import (
        get_most_recent_recording_path,
    )

    export_to_blender(get_most_recent_recording_path())
