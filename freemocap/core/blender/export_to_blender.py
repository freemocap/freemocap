import logging
from pathlib import Path
from typing import Union

from freemocap.core.blender.helpers.freemocap_blender_addon_helpers.run_freemocap_blender_addon_main import \
    run_blender_addon_subprocess
from freemocap.core.blender.helpers.get_best_guess_of_blender_path import get_best_guess_of_blender_path

logger = logging.getLogger(__name__)


def export_to_blender(
        recording_folder_path: Union[str, Path],
        blender_file_path: Union[str, Path],
        blender_exe_path: Union[str, Path],
        method: str = "freemocap_blender_addon",
):
    logger.info(
        f"Exporting session data to a Blender scene at: {str(blender_file_path)} using Blender executable at {str(blender_exe_path)}"
    )

    if method == "freemocap_blender_addon":
        run_blender_addon_subprocess(
            recording_folder_path=recording_folder_path,
            blender_file_path=blender_file_path,
            blender_exe_path=blender_exe_path,
        )

    logger.info("Done with Blender Export :D")


if __name__ == "__main__":
    from freemocap.system.default_paths import FREEMOCAP_TEST_DATA_PATH
    _recording_path = FREEMOCAP_TEST_DATA_PATH

    _blender_output_file = str(Path(_recording_path) / f"{Path(_recording_path).stem}.blend")
    export_to_blender(recording_folder_path=_recording_path,
                      blender_file_path=_blender_output_file,
                      blender_exe_path=get_best_guess_of_blender_path())
