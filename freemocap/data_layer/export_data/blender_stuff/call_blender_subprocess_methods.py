import logging
import subprocess
from pathlib import Path
from typing import Union

# blender_exe_path = (
#     r"C:\Users\jonma\Blender Foundation\stable\blender-3.1.0-windows-x64\blender.exe"
# )
# blender_exe_path = r"C:\Users\jonma\Blender Foundation\Blender 3.1\blender.exe"
from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.data_models.mediapipe_skeleton_names_and_connections import (
    mediapipe_names_and_connections_dict,
)
from freemocap.system.paths_and_filenames.file_and_folder_names import OUTPUT_DATA_FOLDER_NAME
from freemocap.utilities.save_dictionary_to_json import save_dictionary_to_json

logger = logging.getLogger(__name__)


def call_blender_subprocess_cgtinker(
    recording_folder_path: Union[str, Path],
    blender_file_path: Union[str, Path],
    blender_exe_path: Union[str, Path],
):
    path_to_this_py_file = Path(__file__).parent.resolve()

    blender_script_path = path_to_this_py_file / "cgtinker_blendarmocap_load.py"

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
        str(blender_script_path),
        "--",
        str(recording_folder_path),
        str(blender_file_path),
        "1",  # bind to rig
        "1",  # load synchronized_videos
        "9999",  # timeout
        "0",  # load raw data
        "1,",  # load quick
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


def call_blender_subprocess_alpha_megascript(
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


def call_blender_subprocess_megascript_take2(
    recording_folder_path: Union[str, Path],
    blender_file_path: Union[str, Path],
    blender_exe_path: Union[str, Path],
):
    path_to_this_py_file = Path(__file__).parent.resolve()

    freemocap_blender_megascript_path = (
        path_to_this_py_file / "blender_bpy_export_scripts" / "freemocap_blender_megascript_take2.py"
    )

    if not (
        Path(recording_folder_path) / OUTPUT_DATA_FOLDER_NAME / "mediapipe_names_and_connections_dict.json"
    ).is_file():
        save_dictionary_to_json(
            save_path=str(Path(recording_folder_path) / OUTPUT_DATA_FOLDER_NAME),
            file_name="mediapipe_names_and_connections_dict.json",
            dictionary=mediapipe_names_and_connections_dict,
        )

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
