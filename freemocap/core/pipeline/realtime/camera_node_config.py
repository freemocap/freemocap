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
    skeleton_detector_config: SkeletonDetectorConfig|None = Field(default_factory=lambda: RTMPoseDetectorConfig(mode="lightweight",
                                                                                                                confidence_threshold=0.0025,
                                                                                                                max_persons=1))
    # skeleton_detector_config: LegacyMediapipeDetectorConfig|None = Field(default_factory=LegacyMediapipeDetectorConfig)

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

    @property
    def tracking2d_enabled(self) -> bool:
        return self.charuco_tracking_enabled or self.skeleton_tracking_enabled
