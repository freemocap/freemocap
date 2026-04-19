from pydantic import BaseModel, ConfigDict, Field
from skellytracker.trackers.base_tracker.detector_helpers import DetectorConfig
from skellytracker.trackers.rtmpose_tracker.rtmpose_detector import RTMPoseDetectorConfig

from freemocap.core.tasks.calibration.calibration_task_config import CalibrationSource




class PosthocMocapPipelineConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    detector_config: DetectorConfig = Field(default_factory= RTMPoseDetectorConfig)#LegacyMediapipeDetectorConfig)
    calibration_source: CalibrationSource = Field(
        default=CalibrationSource.MOST_RECENT,
        alias="calibrationSource",
        description="How to select the calibration: 'most_recent' uses the latest successful calibration, 'specified' uses calibration_toml_path.",
    )
    calibration_toml_path: str | None = Field(
        default=None,
        alias="calibrationTomlPath",
        description="Path to calibration TOML. Only used when calibration_source is 'specified'.",
    )


    @classmethod
    def default_realtime(cls) -> "PosthocMocapPipelineConfig":
        # return cls(detector_config=RTMPoseDetectorConfig())
        return cls(detector_config=RTMPoseDetectorConfig())

    @classmethod
    def default_posthoc(cls) -> "PosthocMocapPipelineConfig":
        return cls(detector_config=RTMPoseDetectorConfig())

    # @classmethod
    # def default_realtime(cls) -> "PosthocMocapPipelineConfig":
    #     # return cls(detector_config=RTMPoseDetectorConfig())
    #     return cls(detector_config=MediapipeDetectorConfig(
    #         pose_config=MediapipePoseConfig(model_complexity=MediapipePoseModelComplexity.LITE)
    #     ))
    #
    # @classmethod
    # def default_posthoc(cls) -> "PosthocMocapPipelineConfig":
    #     return cls(detector_config=LegacyMediapipeDetectorConfig())
