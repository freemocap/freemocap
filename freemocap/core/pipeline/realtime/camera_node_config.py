from pydantic import BaseModel, Field
from skellytracker.trackers.base_tracker.detector_helpers import SkeletonDetectorConfig
from skellytracker.trackers.charuco_tracker.charuco_tracker_config import CharucoDetectorConfig
from skellytracker.trackers.rtmpose_tracker.rtmpose_detector import RTMPoseDetectorConfig


class CameraNodeConfig(BaseModel):
    charuco_tracking_enabled: bool = True
    skeleton_tracking_enabled: bool = True
    charuco_detector_config: CharucoDetectorConfig|None = Field(default_factory=CharucoDetectorConfig)
    skeleton_detector_config: SkeletonDetectorConfig|None = Field(default_factory=lambda: RTMPoseDetectorConfig(mode="lightweight",
                                                                                                                confidence_threshold=4))
    # skeleton_detector_config: LegacyMediapipeDetectorConfig|None = Field(default_factory=LegacyMediapipeDetectorConfig)

    @property
    def tracking2d_enabled(self) -> bool:
        return self.charuco_tracking_enabled or self.skeleton_tracking_enabled
