from pathlib import Path
from typing import Union

from pydantic import BaseModel

from freemocap.configuration.paths_and_files_names import (
    get_last_successful_calibration_toml_path,
    get_most_recent_recording_path,
    OUTPUT_DATA_FOLDER_NAME,
    SYNCHRONIZED_VIDEOS_FOLDER_NAME,
)
from freemocap.core_processes.capture_volume_calibration.anipose_camera_calibration.get_anipose_calibration_object import (
    load_anipose_calibration_toml_from_path,
)


class MediapipeParametersModel(BaseModel):
    model_complexity: int = 2
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    static_image_mode: bool = False


class AniposeTriangulate3DParametersModel(BaseModel):
    confidence_threshold_cutoff: float = 0.7
    use_triangulate_ransac_method: bool = False


class ButterworthFilterParametersModel(BaseModel):
    sampling_rate: float = 30
    cutoff_frequency: float = 7
    order: int = 4


class PostProcessingParametersModel(BaseModel):
    framerate: float = 30.0
    butterworth_filter_parameters = ButterworthFilterParametersModel()


class SessionInfoModel(BaseModel):
    path_to_session_folder: Union[Path, str] = get_most_recent_recording_path()
    path_to_output_data_folder: Union[Path, str] = get_most_recent_recording_path(
        OUTPUT_DATA_FOLDER_NAME
    )
    path_to_folder_of_synchronized_videos: Union[
        Path, str
    ] = get_most_recent_recording_path(SYNCHRONIZED_VIDEOS_FOLDER_NAME)
    path_to_calibration_toml_file: Union[
        Path, str
    ] = get_last_successful_calibration_toml_path()


class SessionProcessingParameterModel(BaseModel):
    session_info: SessionInfoModel = SessionInfoModel()
    mediapipe_parameters: MediapipeParametersModel = MediapipeParametersModel()
    anipose_triangulate_3d_parameters: AniposeTriangulate3DParametersModel = (
        AniposeTriangulate3DParametersModel()
    )
    post_processing_parameters: PostProcessingParametersModel = (
        PostProcessingParametersModel()
    )

    class Config:
        arbitrary_types_allowed = True
