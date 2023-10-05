import logging
from pathlib import Path
from typing import Optional, Union

from freemocap.core_processes.process_motion_capture_videos.process_recording_folder import process_recording_folder
from freemocap.data_layer.export_data.blender_stuff.export_to_blender import export_to_blender
from freemocap.data_layer.recording_models.post_processing_parameter_models import PostProcessingParameterModel
from freemocap.data_layer.recording_models.recording_info_model import RecordingInfoModel
from freemocap.system.paths_and_filenames.file_and_folder_names import RECORDING_PARAMETERS_JSON_FILE_NAME
from freemocap.system.paths_and_filenames.path_getters import get_blender_file_path
from freemocap.utilities.save_dictionary_to_json import save_dictionary_to_json


def process_folder_of_session_folders(
    path_to_folder_of_session_folders: Union[str, Path],
    path_to_camera_calibration_toml: Optional[Union[str, Path]] = None,
    path_to_blender_executable: Optional[Union[str, Path]] = None,
):
    # list_of_session_folders = list(path_to_folder_of_session_folders.glob("ses*"))
    list_of_session_folders = [f for f in path_to_folder_of_session_folders.iterdir() if f.is_dir()]
    print(list_of_session_folders)

    for session_folder_path in list_of_session_folders:
        logging.info(f"Looking in {session_folder_path} for recording folders")
        list_of_recording_folders = [
            f
            for f in session_folder_path.iterdir()
            if f.is_dir() and (f / "synchronized_videos").exists() and any((f / "synchronized_videos").iterdir())
        ]

        calibration_files = [
            toml_file for sesh in list_of_recording_folders for toml_file in list(sesh.glob("*calibration.toml"))
        ]

        for recording_folder_path in list_of_recording_folders:
            logging.info("Looking for calibration toml")
            if calibration_files:
                this_recording_calibration_toml_path = calibration_files[0]
                logging.info(f"Using {this_recording_calibration_toml_path} for this recording")
            else:
                this_recording_calibration_toml_path = path_to_camera_calibration_toml
                logging.info("Using manually entered calibration for this recording")

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
    rec = PostProcessingParameterModel()

    rec.recording_info_model = RecordingInfoModel(recording_folder_path=Path(recording_path))

    if path_to_camera_calibration_toml:
        rec.recording_info_model.calibration_toml_path = Path(path_to_camera_calibration_toml)
    else:
        logging.warning("No camera calibration toml file provided. May cause an error with multicamera recordings.")

    recording_info_dict = rec.dict(exclude={"recording_info_model"})

    Path(rec.recording_info_model.output_data_folder_path).mkdir(parents=True, exist_ok=True)

    save_dictionary_to_json(
        save_path=rec.recording_info_model.output_data_folder_path,
        file_name=RECORDING_PARAMETERS_JSON_FILE_NAME,
        dictionary=recording_info_dict,
    )

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
    path_to_folder_of_session_folders = Path(r"D:\footropter_pilot_04_19_23\1.0_recordings")

    # Add path to camera calibration toml file you would like to default to
    path_to_camera_calibration_toml = None

    path_to_blender_executable = Path(r"C:\Program Files\Blender Foundation\Blender 3.1\blender.exe")

    process_folder_of_session_folders(
        path_to_folder_of_session_folders=path_to_folder_of_session_folders,
        path_to_camera_calibration_toml=path_to_camera_calibration_toml,
        path_to_blender_executable=path_to_blender_executable,
    )
