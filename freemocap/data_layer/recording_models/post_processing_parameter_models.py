import logging

from pydantic import BaseModel

from freemocap.data_layer.recording_models.recording_info_model import (
    RecordingInfoModel,
)

logger = logging.getLogger(__name__)


class MediapipeParametersModel(BaseModel):
    mediapipe_model_complexity: int = 2
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    static_image_mode: bool = False
    skip_2d_image_tracking: bool = False
    use_multiprocessing: bool = False


class AniposeTriangulate3DParametersModel(BaseModel):
    confidence_threshold_cutoff: float = 0.5
    use_triangulate_ransac_method: bool = False
    skip_3d_triangulation: bool = False


class ButterworthFilterParametersModel(BaseModel):
    sampling_rate: float = 30
    cutoff_frequency: float = 7
    order: int = 4


class PostProcessingParametersModel(BaseModel):
    framerate: float = 30.0
    butterworth_filter_parameters: ButterworthFilterParametersModel = ButterworthFilterParametersModel()
    max_gap_to_fill: int = 10
    skip_butterworth_filter: bool = False


class PostProcessingParameterModel(BaseModel):
    recording_info_model: RecordingInfoModel = None
    mediapipe_parameters_model: MediapipeParametersModel = MediapipeParametersModel()
    anipose_triangulate_3d_parameters_model: AniposeTriangulate3DParametersModel = AniposeTriangulate3DParametersModel()
    post_processing_parameters_model: PostProcessingParametersModel = PostProcessingParametersModel()

    class Config:
        arbitrary_types_allowed = True
