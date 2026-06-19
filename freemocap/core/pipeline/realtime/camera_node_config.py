from pydantic import BaseModel, Field
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellytracker.trackers.base_tracker.detector_helpers import SkeletonDetectorConfig
from skellytracker.trackers.charuco_tracker.charuco_tracker_config import CharucoDetectorConfig
from skellytracker.trackers.rtmpose_tracker.rtmpose_detector_config import RTMPoseDetectorConfig


class CameraNodeConfig(BaseModel):
    worker_mode: WorkerMode = WorkerMode.PROCESS
    charuco_tracking_enabled: bool = True
    skeleton_tracking_enabled: bool = True
    charuco_detector_config: CharucoDetectorConfig|None = Field(default_factory=CharucoDetectorConfig)
    # max_persons=1: we only support single-person tracking for now. Capping
    # detections to one crop per camera keeps the pose batch a fixed size
    # (N cameras), which prevents the ONNX Runtime GPU arena from growing on
    # frames with spurious detections (the cause of intermittent OOMs). Bump to
    # a higher value or None when multi-person tracking lands.
    skeleton_detector_config: SkeletonDetectorConfig|None = Field(default_factory=lambda: RTMPoseDetectorConfig(mode="performance",
                                                                                                                confidence_threshold=5,
                                                                                                                max_persons=1))
    # skeleton_detector_config: LegacyMediapipeDetectorConfig|None = Field(default_factory=LegacyMediapipeDetectorConfig)

    @property
    def tracking2d_enabled(self) -> bool:
        return self.charuco_tracking_enabled or self.skeleton_tracking_enabled
