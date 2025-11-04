from pydantic import BaseModel, model_validator, Field
from skellycam.core.camera.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.types.type_overloads import CameraIdString

from skellytracker.trackers.charuco_tracker.charuco_detector import CharucoDetectorConfig


from skellycam.core.recorders.videos.recording_info import RecordingInfo


class CalibrationTaskConfig(BaseModel):
    calibration_recording_info: RecordingInfo|None = None
    live_track_charuco: bool = True
    detector_config: CharucoDetectorConfig = Field(default_factory=CharucoDetectorConfig)
    minimum_required_cameras: int = 2
    min_shared_views_per_camera: int = 300
    auto_stop_on_min_view_count: bool = True
    auto_process_recording: bool = True

    @property
    def calibration_recording_path(self) -> str:
        return self.calibration_recording_info.full_recording_path

class MocapTaskConfig(BaseModel):
    pass





class PipelineConfig(BaseModel):
    camera_configs: CameraConfigs
    calibration_task_config: CalibrationTaskConfig = Field(default_factory=CalibrationTaskConfig)
    mocap_task_config: MocapTaskConfig = Field(default_factory=MocapTaskConfig)


    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.camera_configs.keys())


    @classmethod
    def from_camera_configs(cls, *, camera_configs: CameraConfigs) -> "PipelineConfig":
        return cls(
            camera_configs=camera_configs,

        )