from typing import Literal

from pydantic import BaseModel, Field
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellytracker.trackers.base_tracker.detector_helpers import SkeletonDetectorConfig
from skellytracker.trackers.charuco_tracker.charuco_tracker_config import CharucoDetectorConfig
from skellytracker.trackers.rtmpose_tracker.rtmpose_detector import RTMPoseDetectorConfig


class CameraNodeConfig(BaseModel):
    worker_mode: WorkerMode = WorkerMode.PROCESS
    charuco_tracking_enabled: bool = True
    skeleton_tracking_enabled: bool = True
    # Mirrored from RealtimePipelineConfig for worker subprocesses.
    realtime_detector_kind: Literal["rtmpose", "mediapipe_js"] = "rtmpose"
    realtime_model_size: Literal["lite", "full", "heavy"] = "full"
    use_centralized_gpu_inference: bool = True
    charuco_detector_config: CharucoDetectorConfig|None = Field(default_factory=CharucoDetectorConfig)
    skeleton_detector_config: SkeletonDetectorConfig|None = Field(default_factory=lambda: RTMPoseDetectorConfig(mode="balanced",
                                                                                                                confidence_threshold=5))
    # skeleton_detector_config: LegacyMediapipeDetectorConfig|None = Field(default_factory=LegacyMediapipeDetectorConfig)

    @property
    def tracking2d_enabled(self) -> bool:
        return self.charuco_tracking_enabled or self.skeleton_tracking_enabled

    @property
    def skip_inline_skeleton_detection(self) -> bool:
        """When True, per-camera RTMPose must not run (centralized GPU or browser MediaPipe)."""
        return (
            (self.use_centralized_gpu_inference and self.realtime_detector_kind == "rtmpose")
            or self.realtime_detector_kind == "mediapipe_js"
        )
