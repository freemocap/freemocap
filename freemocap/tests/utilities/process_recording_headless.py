import logging
from pathlib import Path
from typing import Optional, Union

from freemocap.core_processes.process_motion_capture_videos.process_recording_folder import process_recording_folder
from freemocap.export_data.blender_stuff.export_to_blender import export_to_blender
from freemocap.export_data.generate_jupyter_notebook.generate_jupyter_notebook import generate_jupyter_notebook
from freemocap.parameter_info_models.recording_info_model import RecordingInfoModel
from freemocap.parameter_info_models.recording_processing_parameter_models import RecordingProcessingParameterModel
from freemocap.system.paths_and_files_names import RECORDING_PARAMETER_DICT_JSON_FILE_NAME, get_blender_file_path
from freemocap.utilities.save_dictionary_to_json import save_dictionary_to_json
from freemocap.utilities.get_video_paths import get_video_paths


logger = logging.getLogger(__name__)


def process_recording_headless(
        recording_path: Union[str, Path],
        path_to_camera_calibration_toml: Optional[Union[str, Path]] = None,
        path_to_blender_executable: Optional[Union[str, Path]] = None,
        recording_processing_parameter_model: Optional[
            RecordingProcessingParameterModel] = RecordingProcessingParameterModel(),
):
    rec = recording_processing_parameter_model

    logger.info(f"Processing recording:\n"
                f"Recording path: {recording_path}\n"
                f"Camera calibration toml path: {path_to_camera_calibration_toml}\n"
                f"Blender executable path: {path_to_blender_executable}\n"
                f"Recording processing parameter model: {rec.dict()}")

    rec.recording_info_model = RecordingInfoModel(recording_folder_path=Path(recording_path))

    if path_to_camera_calibration_toml:
        rec.recording_info_model.calibration_toml_path = Path(path_to_camera_calibration_toml)
    else:
        number_of_videos = len(get_video_paths(rec.recording_info_model.synchronized_videos_folder_path))
        if number_of_videos > 1:
            raise ValueError(f"There are {number_of_videos} videos. Must provide a calibration toml file for multicamera recordings.")



    recording_info_dict = rec.dict(exclude={'recording_info_model'})

    Path(rec.recording_info_model.output_data_folder_path).mkdir(parents=True, exist_ok=True)

    save_dictionary_to_json(
        save_path=rec.recording_info_model.output_data_folder_path,
        file_name=RECORDING_PARAMETER_DICT_JSON_FILE_NAME,
        dictionary=recording_info_dict,
    )

    logger.info("Starting core processing pipeline...")

    process_recording_folder(recording_processing_parameter_model=rec)

    logger.info("Generating jupyter notebook...")
    generate_jupyter_notebook(path_to_recording=recording_path)

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
    for file in Path(recording_path).glob('*calibration.toml'):
        return Path(file)


if __name__ == "__main__":
    recording_path = Path("PATH/TO/RECORDING/FOLDER")
    blender_path = Path("PATH/TO/BLENDER/EXECUTABLE")

    process_recording_headless(recording_path=recording_path, path_to_blender_executable=blender_path)
