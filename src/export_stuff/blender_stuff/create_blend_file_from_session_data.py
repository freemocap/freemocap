import subprocess
from pathlib import Path
from typing import Union

from src.config.home_dir import get_session_folder_path

blender_exe_path = (
    r"C:\Users\jonma\Blender Foundation\stable\blender-3.1.0-windows-x64\blender.exe"
)
# blender_exe_path = r"C:\Users\jonma\Blender Foundation\Blender 3.1\blender.exe"

import logging

logger = logging.getLogger(__name__)


def create_blend_file_from_session_data(
    session_folder_path: Union[str, Path], good_clean_frame_number: int = 0
):
    path_to_this_py_file = Path(__file__).parent.resolve()
    freemocap_blender_megascript_path = (
        path_to_this_py_file / "alpha_freemocap_blender_megascript.py"
    )

    command_str = (
        str(blender_exe_path)
        + " --background"
        + " --python "
        + str(freemocap_blender_megascript_path)
        + " -- "
        + session_folder_path
        + " "
        + str(good_clean_frame_number)
    )

    logger.info(f"Starting `blender` sub-process with this command: \n {command_str}")

    blender_process = subprocess.Popen(
        command_str, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    while True:
        output = blender_process.stdout.readline()
        if blender_process.poll() is not None:
            break
        if output:
            print(output.strip().decode())

    if blender_process.returncode == 0:
        print("Blender returned an error:")
        print(blender_process.stderr.read().decode())
    print(f"done with blender stuff :D")
