import inspect
import logging
import subprocess
from pathlib import Path
from typing import Union, List

from ajc27_freemocap_blender_addon.run_as_main import ajc27_run_as_main_function

from freemocap.core_processes.export_data.blender_stuff.export_to_blender.methods.ajc_addon.get_numpy_path import \
    get_numpy_path
from freemocap.core_processes.export_data.blender_stuff.export_to_blender.methods.ajc_addon.install.install_ajc_addon import \
    install_ajc_addon
from freemocap.core_processes.export_data.blender_stuff.export_to_blender.methods.ajc_addon.run_simple import run_simple

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
    ajc_addon_main_file_path = inspect.getfile(ajc27_run_as_main_function)
    logger.info(f"Running ajc27_freemocap_blender_addon as a subprocess using script at : {ajc_addon_main_file_path}")

    addon_root_directory = str(Path(ajc_addon_main_file_path).parent.parent)

    # path_to_blenders_numpy = get_blenders_numpy(blender_exe_path=blender_exe_path)
    # blender_numpy_root = str(Path(path_to_blenders_numpy).parent.parent)

    install_ajc_addon(blender_exe_path=blender_exe_path,
                      ajc_addon_main_file_path=ajc_addon_main_file_path)
    try:
        blender_exe_path = Path(blender_exe_path)
        if not blender_exe_path.exists():
            raise FileNotFoundError(f"Could not find the blender executable at {blender_exe_path}")
    except Exception as e:
        logger.error(e)
        return
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

    blender_process = run_subprocess(command_list=command_list,
                                     append_to_python_path=[addon_root_directory])  # , blender_numpy_root])

    while True:
        output = blender_process.stdout.readline()
        if blender_process.poll() is not None:
            break
        if output:
            print(output.strip().decode())

    if blender_process.returncode != 0:
        print(blender_process.stderr.read().decode())
    logger.info("Done with blender stuff :D")
    blender_process.terminate()  # manually terminate the process


def get_blenders_numpy(blender_exe_path: Union[str, Path]) -> str:
    import subprocess
    get_numpy_script_path = inspect.getfile(get_numpy_path)

    command = [str(blender_exe_path),
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
