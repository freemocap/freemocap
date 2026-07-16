from pydantic import BaseModel, ConfigDict, Field
from skellytracker.core import DetectionStageConfig, TrackerConfig
from skellytracker.core.detectors.keypoint_detectors.rtmpose import RTMPoseDetectorConfig
from skellytracker.core.detectors.object_detectors.yolox import YoloxPersonDetectorConfig
from skellytracker.core.temporal_processing.temporal_processing_config import (
    BBoxPolicyConfig,
    KeypointsWithinBBoxRatioConfig,
)


def _default_mocap_tracker_config() -> TrackerConfig:
    return TrackerConfig(
        stages=[
            DetectionStageConfig(
                name="body",
                object_detector=YoloxPersonDetectorConfig(),
                keypoint_detectors=[RTMPoseDetectorConfig()],
                bbox_policy=BBoxPolicyConfig(
                    redetect_interval=5,
                    keypoint_bbox_expansion=0.2,
                    fitness_checks=[KeypointsWithinBBoxRatioConfig(threshold=0.6)],
                ),
            )
        ]
    )


class PosthocMocapPipelineConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tracker_config: TrackerConfig = Field(default_factory=_default_mocap_tracker_config)
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
