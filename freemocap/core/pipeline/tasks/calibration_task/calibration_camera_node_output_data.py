from skellycam.core.frames.payloads.metadata.frame_metadata import FrameMetadata
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation, \
    DetectedCharucoCornersImageCoordinates

from freemocap.core.pipeline.processing_pipeline import BaseCameraNodeOutputData


class CalibrationCameraNodeOutputData(BaseCameraNodeOutputData):
    frame_metadata: FrameMetadata
    charuco_observation: CharucoObservation

    @property
    def can_see_target(self) -> bool:
        return not self.charuco_observation.charuco_empty

    @property
    def image_size(self):
        return self.frame_metadata.image_size

    @property
    def frame_number(self):
        return self.frame_metadata.frame_number

    @property
    def camera_id(self):
        return self.frame_metadata.camera_id

    @property
    def target_pixel_points(self) -> DetectedCharucoCornersImageCoordinates:
        return self.charuco_observation.detected_charuco_corners_in_full_array
