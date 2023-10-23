import logging
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)


@contextmanager
def run_process(command_list):
    process = subprocess.Popen(command_list, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        yield process
    finally:
        process.terminate()


def call_blender_subprocess_ajc_addon(
        recording_folder_path: Union[str, Path],
        blender_file_path: Union[str, Path],
        blender_exe_path: Union[str, Path],
):
    ajc_addon_main_file_path = Path(
        __file__).parent.parent.resolve() / "ajc27_freemocap_blender_addon" / "freemocap_adapter" / "main.py"

    if not ajc_addon_main_file_path.exists():
        raise FileNotFoundError(f"Could not find the ajc_addon_main_file at {ajc_addon_main_file_path}")

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
        str(ajc_addon_main_file_path),
        "--",
        str(recording_folder_path),
        str(blender_file_path),
    ]

    logger.info(f"Starting `blender` sub-process with this command: \n {command_list}")

    with run_process(command_list) as blender_process:
        while True:
            output = blender_process.stdout.readline()
            if blender_process.poll() is not None:
                break
            if output:
                print(output.strip().decode())

        if blender_process.returncode != 0:
            print(blender_process.stderr.read().decode())
        logger.info("Done with blender stuff :D")


if __name__ == "__main__":
    from freemocap.data_layer.export_data.blender_stuff.get_best_guess_of_blender_path import \
        get_best_guess_of_blender_path

    recording_path_in = r"C:\Users\jonma\freemocap_data\recording_sessions\freemocap_sample_data"
    blender_file_path_in = str(Path(recording_path_in) / (str(Path(recording_path_in).stem)+".blend"))
    blender_exe_path_in = get_best_guess_of_blender_path()

    call_blender_subprocess_ajc_addon(
        recording_folder_path=recording_path_in,
        blender_file_path=blender_file_path_in,
        blender_exe_path=blender_exe_path_in,
    )
