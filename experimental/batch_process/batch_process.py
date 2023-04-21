import logging
from pathlib import Path
from typing import Optional, Union

from freemocap.core_processes.process_motion_capture_videos.process_recording_folder import process_recording_folder
from freemocap.core_processes.export_data.blender_stuff.export_to_blender import export_to_blender
from freemocap.parameter_info_models.recording_info_model import RecordingInfoModel
from freemocap.parameter_info_models.recording_processing_parameter_models import RecordingProcessingParameterModel
from freemocap.system.paths_and_files_names import get_blender_file_path

def process_folder_of_session_folders(
    path_to_folder_of_session_folders: Union[str, Path], 
    path_to_camera_calibration_toml: Optional[Union[str, Path]] = None,
    path_to_blender_executable: Optional[Union[str, Path]] = None,
):
    list_of_session_folders = list(path_to_folder_of_session_folders.glob("ses*"))
    print(list_of_session_folders)

    for session_folder_path in list_of_session_folders:
        logging.info(f"Looking in {session_folder_path} for recording folders")
        for recording_folder_path in list(session_folder_path.glob("rec*")):
            logging.info(f"Looking for calibration toml")
            calibration_files = list(recording_folder_path.glob("*calibration.toml"))

            if calibration_files:
                this_recording_calibration_toml_path = calibration_files[0]
                logging.info(f"Using {this_recording_calibration_toml_path} for this recording")
            else:
                this_recording_calibration_toml_path = path_to_camera_calibration_toml
                logging.info(f"Using manually entered calibration for this recording")

            logging.info(f"Processing {recording_folder_path}")

            process_recording_without_gui(
                recording_path=recording_folder_path,
                path_to_blender_executable=path_to_blender_executable,
                path_to_camera_calibration_toml=this_recording_calibration_toml_path,
            )

    logging.info("Done!")
                                      

def process_recording_without_gui(
    recording_path: Union[str, Path],
    path_to_camera_calibration_toml: Optional[Union[str, Path]] = None,
    path_to_blender_executable: Optional[Union[str, Path]] = None,
):
    rec = RecordingProcessingParameterModel()

    rec.recording_info_model = RecordingInfoModel(recording_folder_path=Path(recording_path))

    if path_to_camera_calibration_toml:
        rec.recording_info_model.calibration_toml_path = Path(path_to_camera_calibration_toml)
    else:
        logging.warning("No camera calibration toml file provided. May cause an error with multicamera recordings.")

    process_recording_folder(recording_processing_parameter_model=rec)

    if path_to_blender_executable:
        blender_file_path = get_blender_file_path(recording_folder_path=recording_path)
        logging.info(f"Exporting to {blender_file_path}")
        export_to_blender(
            recording_folder_path=recording_path,
            blender_file_path=blender_file_path,
            blender_exe_path=Path(path_to_blender_executable),
        )
    else:
        logging.warning("No blender executable provided. Blender file will not be exported.")

if __name__ == "__main__":
    path_to_folder_of_session_folders = Path("PATH_TO_FOLDER_OF_SESSION_FOLDERS")

    # Add path to camera calibration toml file you would like to default to
    path_to_camera_calibration_toml = Path(
        "PATH_TO_CAMERA_CALIBRATION_TOML"
    )

    path_to_blender_executable = Path("PATH_TO_BLENDER_EXECUTABLE")

    process_folder_of_session_folders(
        path_to_folder_of_session_folders=path_to_folder_of_session_folders,
        path_to_camera_calibration_toml=path_to_camera_calibration_toml,
        path_to_blender_executable=path_to_blender_executable,
    )