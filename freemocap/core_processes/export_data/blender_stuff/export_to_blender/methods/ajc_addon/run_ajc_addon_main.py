import inspect
import logging
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Union, List

from ajc27_freemocap_blender_addon.run_as_main import ajc27_run_as_main_function

logger = logging.getLogger(__name__)


@contextmanager
def run_subprocess(command_list: List[str], addon_root_directory: str):
    logger.debug(f"Running subprocess with command list: {command_list}, and addon_root_directory: {addon_root_directory} added to PYTHONPATH")
    modified_env = os.environ.copy()
    # Copy the existing environment variables
    modified_env["PYTHONPATH"] += f";{addon_root_directory}"

    process = subprocess.Popen(command_list, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=modified_env)
    try:
        yield process
    finally:
        process.terminate()

    logger.debug(f"Subprocess finished with return code {process.returncode}")


def run_ajc_blender_addon_subprocess(
        recording_folder_path: Union[str, Path],
        blender_file_path: Union[str, Path],
        blender_exe_path: Union[str, Path],
):
    ajc_addon_main_file_path = inspect.getfile(ajc27_run_as_main_function)
    logger.info(f"Running ajc27_freemocap_blender_addon as a subprocess using script at : {ajc_addon_main_file_path}")

    addon_root_directory = str(Path(ajc_addon_main_file_path).parent.parent)

    path_to_blenders_numpy = get_blenders_numpy()

    # install_ajc_addon(blender_exe_path=blender_exe_path,
    #                   ajc_addon_main_file_path=ajc_addon_main_file_path)

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
        ajc_addon_main_file_path,
        "--",
        str(recording_folder_path),
        str(blender_file_path),

    ]

    logger.info(f"Starting `blender` sub-process with this command: \n {command_list}")

    with run_subprocess(command_list=command_list,
                        addon_root_directory=addon_root_directory) as blender_process:
        while True:
            output = blender_process.stdout.readline()
            if blender_process.poll() is not None:
                break
            if output:
                print(output.strip().decode())

        if blender_process.returncode != 0:
            print(blender_process.stderr.read().decode())
        logger.info("Done with blender stuff :D")


def get_blenders_numpy(blender_exe_path: Union[str, Path] = None) -> str:
    import subprocess
    output = subprocess.check_output([str('path_to_blender_python_executable'), '-c', 'import numpy; print(numpy.__file__)'])
    output_str = output.decode()
    logger.debug(f"Blender's numpy path: {output_str}")
    return output_str


if __name__ == "__main__":
    from freemocap.core_processes.export_data.blender_stuff.get_best_guess_of_blender_path import \
        get_best_guess_of_blender_path

    recording_path_in = r"C:\Users\jonma\freemocap_data\recording_sessions\steen_pantsOn_gait"
    blender_file_path_in = str(Path(recording_path_in) / (str(Path(recording_path_in).stem) + ".blend"))
    blender_exe_path_in = get_best_guess_of_blender_path()

    run_ajc_blender_addon_subprocess(
        recording_folder_path=recording_path_in,
        blender_file_path=blender_file_path_in,
        blender_exe_path=blender_exe_path_in,
    )
