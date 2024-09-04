import inspect
import logging
import subprocess
from pathlib import Path
from typing import Union, List

from ajc27_freemocap_blender_addon.main import ajc27_run_as_main_function

from freemocap.core_processes.export_data.blender_stuff.export_to_blender.methods.ajc_addon.get_numpy_path import (
    get_numpy_path,
)
from freemocap.core_processes.export_data.blender_stuff.export_to_blender.methods.ajc_addon.install.install_ajc_addon import (
    install_ajc_addon,
)
from freemocap.core_processes.export_data.blender_stuff.export_to_blender.methods.ajc_addon.run_simple import run_simple
from freemocap.system.paths_and_filenames.file_and_folder_names import (
    OLD_TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME,
    OLD_SEGMENT_CENTER_OF_MASS_NPY_FILE_NAME,
    OLD_REPROJECTION_ERROR_NPY_FILE_NAME,
    REPROJECTION_ERROR_NPY_FILE_NAME,
    SEGMENT_CENTER_OF_MASS_NPY_FILE_NAME,
    TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME,
)

logger = logging.getLogger(__name__)


def run_subprocess(command_list: List[str], append_to_python_path: List[str] = None):
    logger.debug(f"Running subprocess with command list: {command_list}")
    # modified_env = os.environ.copy()
    # if append_to_python_path is not None:
    #     logger.debug(f"Appending to PYTHONPATH: {append_to_python_path}")
    #     for addon_root_directory in append_to_python_path:
    #         if not Path(addon_root_directory).exists():
    #             raise FileNotFoundError(f"Could not find addon root directory at {addon_root_directory}")
    #         modified_env["PYTHONPATH"] += f";{addon_root_directory}"
    process = subprocess.Popen(command_list, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # env=modified_env)
    return process


def run_ajc_blender_addon_subprocess(
    recording_folder_path: Union[str, Path],
    blender_file_path: Union[str, Path],
    blender_exe_path: Union[str, Path],
):
    try:
        # TODO: pass active tracker into here
        ajc_blender_addon_validator(recording_folder_path=recording_folder_path)
    except FileNotFoundError as e:
        logger.error("Missing required files to run AJC addon, did something go wrong during processing?")
        raise e

    ajc_addon_main_file_path = inspect.getfile(ajc27_run_as_main_function)
    logger.debug(f"Running ajc27_freemocap_blender_addon as a subprocess using script at : {ajc_addon_main_file_path}")

    addon_root_directory = str(Path(ajc_addon_main_file_path).parent.parent)

    # path_to_blenders_numpy = get_blenders_numpy(blender_exe_path=blender_exe_path)
    # blender_numpy_root = str(Path(path_to_blenders_numpy).parent.parent)

    install_ajc_addon(blender_exe_path=blender_exe_path, ajc_addon_main_file_path=ajc_addon_main_file_path)
    try:
        blender_exe_path = Path(blender_exe_path)
        if not blender_exe_path.exists():
            raise FileNotFoundError(f"Could not find the blender executable at {blender_exe_path}")
    except Exception as e:
        logger.error(e)
        raise e

    simple_run_script = inspect.getfile(run_simple)

    command_list = [
        str(blender_exe_path),
        "--background",
        "--python",
        simple_run_script,
        "--",
        str(recording_folder_path),
        str(blender_file_path),
    ]

    logger.info(f"Starting `blender` sub-process with this command: \n {command_list}")

    blender_process = run_subprocess(
        command_list=command_list, append_to_python_path=[addon_root_directory]
    )  # , blender_numpy_root])

    while True:
        output = blender_process.stdout.readline()
        if blender_process.poll() is not None:
            break
        if output:
            logging.debug(output.strip().decode())

    if blender_process.returncode != 0:
        logging.error(blender_process.stderr.read().decode())
    logger.debug("Done with blender add on")
    blender_process.terminate()  # manually terminate the process


def get_blenders_numpy(blender_exe_path: Union[str, Path]) -> str:
    import subprocess

    get_numpy_script_path = inspect.getfile(get_numpy_path)

    command = [
        str(blender_exe_path),
        "--background",
        "--python",
        get_numpy_script_path,
    ]
    subprocess_result = subprocess.run(command, capture_output=True, text=True)
    all_output = subprocess_result.stdout
    numpy_path = None
    for line in all_output.split("\n"):
        if "numpy" in line:
            numpy_path = line
            break
    if not Path(numpy_path).exists():
        raise FileNotFoundError(f"Could not find Blender's numpy at {numpy_path}")
    logger.info(f"Got Blender's numpy path: {numpy_path}")
    return numpy_path


def ajc_blender_addon_validator(recording_folder_path: Union[str, Path], active_tracker: str = "mediapipe"):
    """
    Check if the required files exist in the recording folder
    """
    recording_path = Path(recording_folder_path)
    output_data_path = recording_path / "output_data"

    if active_tracker[-1] != "_":
        active_tracker = active_tracker + "_"

    if not (output_data_path / (active_tracker + "body_3d_xyz.npy")).exists():
        raise FileNotFoundError(
            f"Could not find required file: {output_data_path / (active_tracker + 'body_3d_xyz.npy')}"
        )

    if not (output_data_path / (active_tracker + "right_hand_3d_xyz.npy")).exists():
        raise FileNotFoundError(
            f"Could not find required file: {output_data_path / (active_tracker + 'right_hand_3d_xyz.npy')}"
        )

    if not (output_data_path / (active_tracker + "left_hand_3d_xyz.npy")).exists():
        raise FileNotFoundError(
            f"Could not find required file: {output_data_path / (active_tracker + 'left_hand_3d_xyz.npy')}"
        )

    if not (output_data_path / (active_tracker + "face_3d_xyz.npy")).exists():
        raise FileNotFoundError(
            f"Could not find required file: {output_data_path / (active_tracker + 'face_3d_xyz.npy')}"
        )

    if not (output_data_path / "center_of_mass" / (active_tracker + TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME)).exists():
        if (
            active_tracker != "mediapipe_"
            or not (output_data_path / "center_of_mass" / OLD_TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME).exists()
        ):
            raise FileNotFoundError(
                f"Could not find required file: {output_data_path / 'center_of_mass' / (active_tracker + TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME)}"
            )

    if not (output_data_path / "center_of_mass" / (active_tracker + SEGMENT_CENTER_OF_MASS_NPY_FILE_NAME)).exists():
        if (
            active_tracker != "mediapipe_"
            or not (output_data_path / "center_of_mass" / OLD_SEGMENT_CENTER_OF_MASS_NPY_FILE_NAME).exists()
        ):
            raise FileNotFoundError(
                f"Could not find required file: {output_data_path / 'center_of_mass' / (active_tracker + SEGMENT_CENTER_OF_MASS_NPY_FILE_NAME)}"
            )

    if not (output_data_path / "raw_data" / (active_tracker + REPROJECTION_ERROR_NPY_FILE_NAME)).exists():
        if (
            active_tracker != "mediapipe_"
            or not (output_data_path / "raw_data" / OLD_REPROJECTION_ERROR_NPY_FILE_NAME).exists()
        ):
            raise FileNotFoundError(
                f"Could not find required file: {output_data_path / 'raw_data' / (active_tracker + REPROJECTION_ERROR_NPY_FILE_NAME)}"
            )


if __name__ == "__main__":
    from freemocap.core_processes.export_data.blender_stuff.get_best_guess_of_blender_path import (
        get_best_guess_of_blender_path,
    )

    recording_path_in = r"C:\Users\jonma\freemocap_data\recording_sessions\steen_pantsOn_gait"
    blender_file_path_in = str(Path(recording_path_in) / (str(Path(recording_path_in).stem) + ".blend"))
    blender_exe_path_in = get_best_guess_of_blender_path()

    run_ajc_blender_addon_subprocess(
        recording_folder_path=recording_path_in,
        blender_file_path=blender_file_path_in,
        blender_exe_path=blender_exe_path_in,
    )
