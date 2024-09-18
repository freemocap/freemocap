import logging
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator
from skellytracker.trackers.mediapipe_tracker.mediapipe_model_info import MediapipeTrackingParams, MediapipeModelInfo
from skellytracker.trackers.yolo_tracker.yolo_model_info import YOLOTrackingParams, YOLOModelInfo
from skellytracker.trackers.base_tracker.base_tracking_params import BaseTrackingParams
from skellytracker.trackers.base_tracker.model_info import ModelInfo

from freemocap.data_layer.recording_models.recording_info_model import (
    RecordingInfoModel,
)

logger = logging.getLogger(__name__)


class AniposeTriangulate3DParametersModel(BaseModel):
    run_reprojection_error_filtering: bool = False
    reprojection_error_confidence_cutoff: float = 90
    minimum_cameras_to_reproject: int = 3
    use_triangulate_ransac_method: bool = False
    run_3d_triangulation: bool = True
    flatten_single_camera_data: bool = True


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
    recording_info_model: Optional[RecordingInfoModel] = None
    tracking_parameters_model: BaseTrackingParams = BaseTrackingParams()
    anipose_triangulate_3d_parameters_model: AniposeTriangulate3DParametersModel = AniposeTriangulate3DParametersModel()
    post_processing_parameters_model: PostProcessingParametersModel = PostProcessingParametersModel()
    tracking_model_info: ModelInfo = ModelInfo()

    @model_validator(mode="after")
    def set_tracking_parameters_for_active_tracker(self):
        if self.recording_info_model:
            self.update_tracking_params()
        return self

    def set_recording_info_model(self, recording_info_model: RecordingInfoModel):
        self.set_recording_info_model(recording_info_model)
        self.update_tracking_params()

    def update_tracking_params(self):
        if not self.recording_info_model:
            return
        if self.recording_info_model.active_tracker == "mediapipe":
            self.tracking_parameters_model = MediapipeTrackingParams()
            self.tracking_model_info = MediapipeModelInfo()
        elif self.recording_info_model.active_tracker == "yolo":
            self.tracking_parameters_model = YOLOTrackingParams()
            self.tracking_model_info = YOLOModelInfo()
        else:
            raise ValueError(f"Unknown tracker: {self.recording_info_model.active_tracker}")