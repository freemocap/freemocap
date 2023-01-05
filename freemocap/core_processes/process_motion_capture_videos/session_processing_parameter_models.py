from pathlib import Path
from typing import Union

from pydantic import BaseModel


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


class SessionProcessingParameterModel(BaseModel):

    path_to_session_folder: Union[Path, str] = None
    path_to_output_data_folder: Union[Path, str] = None
    path_to_folder_of_synchronized_videos: Union[Path, str] = None
    anipose_calibration_object: object = None  # I don't wtf that thing is lol
    mediapipe_parameters: MediapipeParametersModel = MediapipeParametersModel()
    anipose_triangulate_3d_parameters: AniposeTriangulate3DParametersModel = (
        AniposeTriangulate3DParametersModel()
    )
    post_processing_parameters: PostProcessingParametersModel = (
        PostProcessingParametersModel()
    )

    class Config:
        arbitrary_types_allowed = True
