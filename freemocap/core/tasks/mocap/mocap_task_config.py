from pydantic import BaseModel, ConfigDict, Field
from skellytracker.trackers.base_tracker.detector_helpers import  SkeletonDetectorConfig
from skellytracker.trackers.rtmpose_tracker.rtmpose_detector import RTMPoseDetectorConfig
from skellytracker.trackers.mediapipe_tracker import MediapipeDetectorConfig


class PosthocMocapPipelineConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    skeleton_detector_config: SkeletonDetectorConfig = Field(default_factory= MediapipeDetectorConfig)#LegacyMediapipeDetectorConfig)
    calibration_toml_path: str | None = Field(
        default=None,
        alias="calibrationTomlPath",
        description="Path to calibration TOML. If None, the most-recent successful calibration is used.",
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

