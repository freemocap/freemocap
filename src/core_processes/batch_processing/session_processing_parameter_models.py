from pathlib import Path
from typing import Union

from pydantic import BaseModel


class MediaPipe2DParametersModel(BaseModel):
    model_complexity: int = 2
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    static_image_mode: bool = False


class AniposeTriangulate3DParametersModel(BaseModel):
    confidence_threshold_cutoff: float = 0.7
    use_triangulate_ransac_method: bool = True


class ButterworthFilterParametersModel(BaseModel):
    sampling_rate: float = 30
    cutoff_frequency: float = 7
    order: int = 4


class PostProcessingParametersModel(BaseModel):
    framerate: float = 30.0
    butterworth_filter_parameters = ButterworthFilterParametersModel()


class SessionProcessingParameterModel(BaseModel):
    path_to_session_folder: Union[Path, str]
    path_to_output_data_folder: Union[Path, str]
    path_to_folder_of_synchronized_videos: Union[Path, str]
    anipose_calibration_object: object  # I don't wtf that thing is lol
    path_to_blender_executable: Union[Path, str]
    mediapipe_2d_parameters: MediaPipe2DParametersModel = MediaPipe2DParametersModel()
    anipose_triangulate_3d_parameters: AniposeTriangulate3DParametersModel = (
        AniposeTriangulate3DParametersModel()
    )
    post_processing_parameters: PostProcessingParametersModel = (
        PostProcessingParametersModel()
    )
    start_processing_at_stage: Union[int, str] = 0

    class Config:
        arbitrary_types_allowed = True
