from pydantic import BaseModel, model_validator, Field, ConfigDict
from skellycam.core.camera.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.types.type_overloads import CameraIdString

from skellytracker.trackers.charuco_tracker.charuco_detector import CharucoDetectorConfig


from skellycam.core.recorders.videos.recording_info import RecordingInfo


class CalibrationTaskConfig(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )
    calibration_recording_folder: str|None = Field(default=None, alias="calibrationRecordingFolder")
    live_track_charuco: bool = Field(default=True,alias="liveTrackCharuco")
    charuco_board_x_squares: int = Field(gt=0, default=3, alias="charucoBoardXSquares")
    charuco_board_y_squares: int = Field(gt=0, default=5, alias="charucoBoardYSquares")
    charuco_square_length: float = Field(gt=0, default=56, alias="charucoSquareLength")
    min_shared_views_per_camera: int = Field(gt=0, default=200, alias="minSharedViewsPerCamera")
    auto_stop_on_min_view_count: bool = Field(default=True, alias="autoStopOnMinViewCount")
    auto_process_recording: bool = Field(default=True, alias="autoProcessRecording")

    @property
    def detector_config(self) -> CharucoDetectorConfig:
        return CharucoDetectorConfig(
            squares_x=self.charuco_board_x_squares,
            squares_y=self.charuco_board_y_squares,
            unscaled_square_length=self.charuco_square_length,
        )


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