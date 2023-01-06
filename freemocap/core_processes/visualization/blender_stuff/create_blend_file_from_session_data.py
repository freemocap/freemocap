import logging
import subprocess
from pathlib import Path
from typing import Union

# blender_exe_path = (
#     r"C:\Users\jonma\Blender Foundation\stable\blender-3.1.0-windows-x64\blender.exe"
# )
# blender_exe_path = r"C:\Users\jonma\Blender Foundation\Blender 3.1\blender.exe"

logger = logging.getLogger(__name__)


def create_blend_file_from_session_data(
    recording_folder_path: Union[str, Path],
    blender_exe_path: Union[str, Path],
    good_clean_frame_number: int = 0,
):
    path_to_this_py_file = Path(__file__).parent.resolve()

    freemocap_blender_megascript_path = (
        path_to_this_py_file / "alpha_freemocap_blender_megascript.py"
    )

    # freemocap_blender_megascript_path = (
    #     path_to_this_py_file / "bind_rigify_meta_rig_to_freemocap_data.py"
    # )

    try:
        blender_exe_path = Path(blender_exe_path)
        if not blender_exe_path.exists():
            raise FileNotFoundError(
                f"Could not find the blender executable at {blender_exe_path}"
            )
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
        str(good_clean_frame_number),
    ]

    logger.info(f"Starting `blender` sub-process with this command: \n {command_list}")

    blender_process = subprocess.Popen(
        command_list, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
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
    logger.info(f"Done with blender stuff :D")
