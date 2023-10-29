import subprocess
from pathlib import Path
from typing import Union

import logging
logger = logging.getLogger(__name__)


def run_alpha_megascript(
    recording_folder_path: Union[str, Path],
    blender_file_path: Union[str, Path],
    blender_exe_path: Union[str, Path],
    good_clean_frame_number: int = 0,
):
    path_to_this_py_file = Path(__file__).parent.resolve()

    freemocap_blender_megascript_path = (
        path_to_this_py_file / "blender_bpy_export_scripts" / "alpha_freemocap_blender_megascript.py"
    )

    # freemocap_blender_megascript_path = (
    #     path_to_this_py_file / "freemocap_blender_megascript_take2.py"
    # )

    try:
        blender_exe_path = Path(blender_exe_path)
        if not blender_exe_path.exists():
            raise FileNotFoundError(f"Could not find the blender executable at {blender_exe_path}")
    except Exception as e:
        logger.error(e)
        return

    command_list = [
        str(blender_exe_path),
        "--background",
        "--python",
        str(freemocap_blender_megascript_path),
        "--",
        str(recording_folder_path),
        str(blender_file_path),
        str(good_clean_frame_number),
    ]

    logger.info(f"Starting `blender` sub-process with this command: \n {command_list}")

    blender_process = subprocess.Popen(command_list, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    while True:
        output = blender_process.stdout.readline()
        if blender_process.poll() is not None:
            break
        if output:
            print(output.strip().decode())

    if blender_process.returncode == 0:
        print("Blender returned an error:")
        print(blender_process.stderr.read().decode())
    logger.info("Done with blender stuff :D")
