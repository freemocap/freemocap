from typing import Literal

from pydantic import BaseModel, Field
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellytracker.core import TrackerConfig, DetectionStageConfig
from skellytracker.core.detectors.keypoint_detectors.charuco import (
    CharucoBoardDefinition,
    CharucoDetectorConfig,
)
from skellytracker.core.detectors.keypoint_detectors.mediapipe.mediapipe_model_manager import (
    MediapipePoseModelComplexity,
)
from skellytracker.core.detectors.keypoint_detectors.rtmpose import RTMPoseDetectorConfig
from skellytracker.core.detectors.object_detectors.yolox import YoloxPersonDetectorConfig
from skellytracker.core.temporal_processing.temporal_processing_config import (
    BBoxPolicyConfig,
    KeypointsWithinBBoxRatioConfig,
)


def _default_skeleton_tracker_config() -> TrackerConfig:
    return TrackerConfig(
        stages=[
            DetectionStageConfig(
                name="body",
                object_detector=YoloxPersonDetectorConfig(),
                keypoint_detectors=[
                    RTMPoseDetectorConfig(
                        model_name="rtmw-x-l_256x192",
                        confidence_threshold=0.0025,
                    )
                ],
                bbox_policy=BBoxPolicyConfig(
                    redetect_interval=5,
                    keypoint_bbox_expansion=0.2,
                    fitness_checks=[KeypointsWithinBBoxRatioConfig(threshold=0.6)],
                ),
            )
        ]
    )


def _default_charuco_tracker_config() -> TrackerConfig:
    return TrackerConfig(
        stages=[
            DetectionStageConfig(
                name="charuco",
                keypoint_detectors=[
                    CharucoDetectorConfig(
                        board=CharucoBoardDefinition.create_letter_size_5x3()
                    )
                ],
            )
        ]
    )


class CameraNodeConfig(BaseModel):
    worker_mode: WorkerMode = WorkerMode.PROCESS
    charuco_tracking_enabled: bool = True
    skeleton_tracking_enabled: bool = True
    detector_type: Literal["rtmpose", "mediapipe"] = "rtmpose"
    # RTMPose config (only used when detector_type="rtmpose")
    rtmpose_model_name: Literal["rtmw-x-l_256x192", "rtmw-x-l_384x288", "rtmw-l-m_256x192"] = "rtmw-x-l_256x192"
    rtmpose_confidence_threshold: float = 0.0025
    # MediaPipe config (only used when detector_type="mediapipe")
    mediapipe_model_complexity: MediapipePoseModelComplexity = MediapipePoseModelComplexity.LITE
    mediapipe_detection_confidence: float = 0.5
    mediapipe_presence_confidence: float = 0.5
    mediapipe_tracking_confidence: float = 0.5
    mediapipe_num_hands: int = 2
    mediapipe_num_faces: int = 1
    charuco_tracker_config: TrackerConfig | None = Field(
        default_factory=_default_charuco_tracker_config
    )
    # max_persons: we only support single-person tracking for now. Capping
    # detections to one crop per camera keeps the pose batch a fixed size
    # (N cameras), which prevents the ONNX Runtime GPU arena from growing on
    # frames with spurious detections (the cause of intermittent OOMs).
    skeleton_tracker_config: TrackerConfig | None = Field(
        default_factory=_default_skeleton_tracker_config
    )

    # ---- 2D keypoint One Euro filter ----
    # When True, applies per-keypoint temporal smoothing to the 2D pixel
    # coordinates coming out of the skeleton detector, before they leave
    # the camera node. Reduces pixel jitter before triangulation.
    enable_keypoint_filter: bool = True
    # Minimum cutoff (Hz) — lower = more smoothing when stationary.
    keypoint_filter_min_cutoff: float = 1.0
    # Speed coefficient. Pixel-space needs much smaller values than mm-space
    # because pixel velocities are ~100× larger numerically. 0.0001 keeps the
    # adaptive cutoff near min_cutoff for typical movements.
    keypoint_filter_beta: float = 0.0001
    # Velocity-estimate filter cutoff (Hz).
    keypoint_filter_d_cutoff: float = 1.0

    # Confidence gating threshold — keypoints below this visibility score
    # have their xy NaN-ed before publication so triangulation skips them.
    confidence_threshold: float = 0.0025

    @property
    def tracking2d_enabled(self) -> bool:
        return self.charuco_tracking_enabled or self.skeleton_tracking_enabled
