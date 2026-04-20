from pydantic import BaseModel, ConfigDict, Field
from skellytracker.trackers.base_tracker.detector_helpers import  SkeletonDetectorConfig
from skellytracker.trackers.rtmpose_tracker.rtmpose_detector import RTMPoseDetectorConfig
from skellytracker.trackers.mediapipe_tracker import MediapipeDetectorConfig

from freemocap.core.tasks.calibration.calibration_task_config import CalibrationSource




class PosthocMocapPipelineConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    skeleton_detector_config: SkeletonDetectorConfig = Field(default_factory= MediapipeDetectorConfig)#LegacyMediapipeDetectorConfig)
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
    export_to_blender: bool = Field(
        default=True,
        alias="exportToBlender",
        description="If True, export the processed mocap recording to a .blend file after processing.",
    )
    blender_exe_path: str | None = Field(
        default=None,
        alias="blenderExePath",
        description="Path to the Blender executable. If None, auto-detect.",
    )
    auto_open_blend_file: bool = Field(
        default=True,
        alias="autoOpenBlendFile",
        description="If True, open the .blend file in Blender after export completes.",
    )


    @classmethod
    def default_realtime(cls) -> "PosthocMocapPipelineConfig":
        # return cls(detector_config=RTMPoseDetectorConfig())
        return cls(skeleton_detector_config=RTMPoseDetectorConfig())

    @classmethod
    def default_posthoc(cls) -> "PosthocMocapPipelineConfig":
        return cls(skeleton_detector_config=RTMPoseDetectorConfig())

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
