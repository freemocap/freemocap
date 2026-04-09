import inspect
import logging
import subprocess
from pathlib import Path
from typing import Union, List

import freemocap_blender_addon

from freemocap.core.blender.helpers.freemocap_blender_addon_helpers.run_simple import run_simple
from freemocap.core.blender.helpers.get_best_guess_of_blender_path import get_best_guess_of_blender_path
from freemocap.utilities.open_file import open_file

logger = logging.getLogger(__name__)

RAW_3D_NPY_FILE_NAME = "3dData_numFrames_numTrackedPoints_spatialXYZ.npy"
REPROJECTION_ERROR_NPY_FILE_NAME = "3dData_numFrames_numTrackedPoints_reprojectionError.npy"
FULL_REPROJECTION_ERROR_NPY_FILE_NAME = "3dData_numCams_numFrames_numTrackedPoints_reprojectionError.npy"
REPROJECTION_FILTERED_PREFIX = "reprojection_filtered_"

DATA_3D_NPY_FILE_NAME = "skeleton_3d.npy"
RIGID_BONES_NPY_FILE_NAME = "rigid_bones_3d.npy"
BODY_3D_DATAFRAME_CSV_FILE_NAME = "body_3d_xyz.csv"
RIGHT_HAND_3D_DATAFRAME_CSV_FILE_NAME = "right_hand_right_hand.csv" # TODO -  the names are duplicated in the right/left hand, needs fixed in skellyforge.skellymodels.human (i think?)
LEFT_HAND_3D_DATAFRAME_CSV_FILE_NAME = "left_hand_left_hand.csv" # TODO -  the names are duplicated in the right/left hand, needs fixed in skellyforge.skellymodels.human (i think?)
FACE_3D_DATAFRAME_CSV_FILE_NAME = "face_3d_xyz.csv"

TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME = "body_total_body_center_of_mass.npy"
SEGMENT_CENTER_OF_MASS_NPY_FILE_NAME = "body_segment_center_of_mass.npy"

OLD_DATA_2D_NPY_FILE_NAME = "mediapipe2dData_numCams_numFrames_numTrackedPoints_pixelXY.npy"
OLD_RAW_3D_NPY_FILE_NAME = "mediapipe3dData_numFrames_numTrackedPoints_spatialXYZ.npy"
OLD_REPROJECTION_ERROR_NPY_FILE_NAME = "mediapipe3dData_numFrames_numTrackedPoints_reprojectionError.npy"
OLD_DATA_3D_NPY_FILE_NAME = "mediaPipeSkel_3d_body_hands_face.npy"
OLD_TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME = "total_body_center_of_mass_xyz.npy"
OLD_SEGMENT_CENTER_OF_MASS_NPY_FILE_NAME = "segmentCOM_frame_joint_xyz.npy"


def run_subprocess(command_list: List[str]):
    logger.debug(f"Running subprocess with command list: {command_list}")
    process = subprocess.Popen(command_list, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return process


def export_to_blender(
        recording_folder_path: str|Path,
        blend_file_path: str|Path|None=None,
        blender_exe_path: str|Path|None=None,
        open_file_on_completion:bool=True,
):
    try:
        freemocap_blender_addon_validator(recording_folder_path=recording_folder_path)
    except FileNotFoundError as e:
        logger.error("Missing required files to run AJC addon, did something go wrong during processing?")
        raise e

    if blender_exe_path is None:
        blender_exe_path:Path = Path(get_best_guess_of_blender_path())
        if not blender_exe_path.is_file():
            raise RuntimeError(f"Blender executable not found at: {blender_exe_path}")
    if blend_file_path is None:
        blend_file_path = Path(recording_folder_path)/f"{Path(recording_folder_path).stem}.blend"

    # Resolve the site-packages directory containing freemocap_blender_addon
    # so we can inject it into Blender's sys.path (no addon installation needed)
    addon_package_path = Path(inspect.getfile(freemocap_blender_addon))
    site_packages_path = str(addon_package_path.parent.parent)
    logger.debug(f"Will inject site-packages path into Blender's sys.path: {site_packages_path}")

    simple_run_script = inspect.getfile(run_simple)

    command_list = [
        str(blender_exe_path),
        "--background",
        "--python",
        simple_run_script,
        "--",
        site_packages_path,
        str(recording_folder_path),
        str(blend_file_path),
    ]

    logger.info(f"Starting `blender` sub-process with this command: \n {command_list}")

    blender_process = run_subprocess(command_list=command_list)

    while True:
        output = blender_process.stdout.readline()
        if blender_process.poll() is not None:
            break
        if output:
            logging.debug(output.strip().decode())

    if blender_process.returncode != 0:
        logging.error(blender_process.stderr.read().decode())
    if not Path(blend_file_path).is_file():
        raise RuntimeError(f"Blender executable not found at: {blend_file_path}")
    elif Path(blend_file_path).stat().st_size == 0:
        raise RuntimeError(f"Blender file was created but is empty at: {blend_file_path}")

    if open_file_on_completion:
        logger.info(f"Opening {blend_file_path} with {blender_exe_path}")
        open_file(blend_file_path,)


    logger.debug("Done with blender add on")
    blender_process.terminate()  # manually terminate the process




def freemocap_blender_addon_validator(recording_folder_path: Union[str, Path], active_tracker: str = "mediapipe"):
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

    if not (output_data_path / (active_tracker + "right_hand_right_hand.npy")).exists(): #duplicated hand dnames need fixed in skforge
        raise FileNotFoundError(
            f"Could not find required file: {output_data_path / (active_tracker + 'right_hand_right_hand.npy')}"
        )

    if not (output_data_path / (active_tracker + "left_hand_left_hand.npy")).exists():
        raise FileNotFoundError(
            f"Could not find required file: {output_data_path / (active_tracker + 'left_hand_left_hand.npy')}"
        )

    if not (output_data_path / (active_tracker + "face_3d_xyz.npy")).exists():
        raise FileNotFoundError(
            f"Could not find required file: {output_data_path / (active_tracker + 'face_3d_xyz.npy')}"
        )

    if not (output_data_path / (active_tracker + TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME)).exists():
        if (
                active_tracker != "mediapipe_"
                or not (output_data_path / OLD_TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME).exists()
        ):
            raise FileNotFoundError(
                f"Could not find required file: {output_data_path  / (active_tracker + TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME)}"
            )

    if not (output_data_path / (active_tracker + SEGMENT_CENTER_OF_MASS_NPY_FILE_NAME)).exists():
        if (
                active_tracker != "mediapipe_"
                or not (output_data_path / OLD_SEGMENT_CENTER_OF_MASS_NPY_FILE_NAME).exists()
        ):
            raise FileNotFoundError(
                f"Could not find required file: {output_data_path / 'center_of_mass' / (active_tracker + SEGMENT_CENTER_OF_MASS_NPY_FILE_NAME)}"
            )

    # if not (output_data_path / "raw_data" / (active_tracker + REPROJECTION_ERROR_NPY_FILE_NAME)).exists():
    #     if (
    #             active_tracker != "mediapipe_"
    #             or not (output_data_path / "raw_data" / OLD_REPROJECTION_ERROR_NPY_FILE_NAME).exists()
    #     ):
    #         raise FileNotFoundError(
    #             f"Could not find required file: {output_data_path / 'raw_data' / (active_tracker + REPROJECTION_ERROR_NPY_FILE_NAME)}"
    #         )


if __name__ == "__main__":


    recording_path_in = r"C:\Users\jonma\freemocap_data\recording_sessions\steen_pantsOn_gait"
    blend_file_path_in = str(Path(recording_path_in) / (str(Path(recording_path_in).stem) + ".blend"))
    blender_exe_path_in = get_best_guess_of_blender_path()

    export_to_blender(
        recording_folder_path=recording_path_in,
        blend_file_path=blend_file_path_in,
        blender_exe_path=blender_exe_path_in,
    )
