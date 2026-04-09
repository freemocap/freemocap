from pydantic import BaseModel, ConfigDict, Field
from skellytracker.trackers.base_tracker.detector_annotation import DetectorConfig
from skellytracker.trackers.legacy_mediapipe_tracker import LegacyMediapipeDetectorConfig
from skellytracker.trackers.mediapipe_tracker import MediapipeDetectorConfig
from skellytracker.trackers.mediapipe_tracker.body.mediapipe_pose_config import MediapipePoseConfig
from skellytracker.trackers.mediapipe_tracker.mediapipe_model_manager import MediapipePoseModelComplexity

from freemocap.core.tasks.calibration.calibration_task_config import CalibrationSource


class PosthocMocapPipelineConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    detector_config: DetectorConfig = Field(default_factory=LegacyMediapipeDetectorConfig)
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

    force_reestimate_groundplane: bool = Field(
        default=False,
        alias="forceReestimateGroundplane",
        description="Re-estimate groundplane even if one was already applied during calibration.",
    )

    @classmethod
    def default_realtime(cls) -> "PosthocMocapPipelineConfig":
        # return cls(detector_config=RTMPoseDetectorConfig())
        return cls(detector_config=MediapipeDetectorConfig(
            pose_config=MediapipePoseConfig(model_complexity=MediapipePoseModelComplexity.LITE)
        ))

    @classmethod
    def default_posthoc(cls) -> "PosthocMocapPipelineConfig":
        return cls(detector_config=LegacyMediapipeDetectorConfig())
