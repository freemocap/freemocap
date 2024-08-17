import logging

from pydantic import ConfigDict, BaseModel
from skellytracker.trackers.mediapipe_tracker.mediapipe_model_info import (
    MediapipeTrackingParams
)

from freemocap.data_layer.recording_models.recording_info_model import (
    RecordingInfoModel,
)

logger = logging.getLogger(__name__)


class AniposeTriangulate3DParametersModel(BaseModel):
    run_reprojection_error_filtering: bool = False
    reprojection_error_confidence_cutoff: float = 90
    minimum_cameras_to_reproject: int = 3
    confidence_threshold_cutoff: float = 0.5
    use_triangulate_ransac_method: bool = False
    run_3d_triangulation: bool = True


class ButterworthFilterParametersModel(BaseModel):
    sampling_rate: float = 30
    cutoff_frequency: float = 7
    order: int = 4


class PostProcessingParametersModel(BaseModel):
    framerate: float = 30.0
    butterworth_filter_parameters: ButterworthFilterParametersModel = ButterworthFilterParametersModel()
    max_gap_to_fill: int = 10
    run_butterworth_filter: bool = True


class ProcessingParameterModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    recording_info_model: RecordingInfoModel = RecordingInfoModel()
    mediapipe_parameters_model: MediapipeTrackingParams = MediapipeTrackingParams()
    anipose_triangulate_3d_parameters_model: AniposeTriangulate3DParametersModel = AniposeTriangulate3DParametersModel()
    post_processing_parameters_model: PostProcessingParametersModel = PostProcessingParametersModel()
