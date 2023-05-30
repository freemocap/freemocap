import logging
from pathlib import Path
from typing import Optional, Union
from freemocap.core_processes.process_motion_capture_videos.process_recording_folder import process_recording_folder
from freemocap.core_processes.export_data.blender_stuff.export_to_blender import export_to_blender
from freemocap.parameter_info_models.recording_info_model import RecordingInfoModel
from freemocap.parameter_info_models.recording_processing_parameter_models import RecordingProcessingParameterModel
from freemocap.system.paths_and_files_names import RECORDING_PARAMETER_DICT_JSON_FILE_NAME, get_blender_file_path
from freemocap.utilities.save_dictionary_to_json import save_dictionary_to_json

logger = logging.getLogger(__name__)


def process_recording_headless(
    recording_path: Union[str, Path],
    path_to_camera_calibration_toml: Optional[Union[str, Path]] = None,
    path_to_blender_executable: Optional[Union[str, Path]] = None,
):
    rec = RecordingProcessingParameterModel()

    rec.recording_info_model = RecordingInfoModel(recording_folder_path=Path(recording_path))

    if path_to_camera_calibration_toml:
        rec.recording_info_model.calibration_toml_path = Path(path_to_camera_calibration_toml)
    else:
        logger.warning("No camera calibration toml file provided. May cause an error with multicamera recordings.")

    recording_info_dict = rec.dict(exclude={'recording_info_model'})

    save_dictionary_to_json(
        save_path=rec.recording_info_model.output_data_folder_path,
        file_name=RECORDING_PARAMETER_DICT_JSON_FILE_NAME,
        dictionary=recording_info_dict,
    )

    process_recording_folder(recording_processing_parameter_model=rec)

    if path_to_blender_executable:
        blender_file_path = get_blender_file_path(recording_folder_path=recording_path)
        logger.info(f"Exporting to {blender_file_path}")
        export_to_blender(
            recording_folder_path=recording_path,
            blender_file_path=blender_file_path,
            blender_exe_path=Path(path_to_blender_executable),
        )
    else:
        logger.warning("No blender executable provided. Blender file will not be exported.")

def find_calibration_toml_path(recording_path: Union[str, Path]) -> Path:
    for file in recording_path.glob('*calibration.toml'):
        return Path(file)

if __name__ == "__main__":
    recording_path = Path("PATH/TO/RECORDING/FOLDER")
    blender_path = Path("PATH/TO/BLENDER/EXECUTABLE")

    process_recording_headless(recording_path=recording_path, path_to_blender_executable=blender_path)
