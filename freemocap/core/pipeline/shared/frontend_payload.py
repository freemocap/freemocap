import logging

from pydantic import BaseModel, ConfigDict
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.image_overlay.charuco_overlay_data import CharucoOverlayData
from freemocap.core.image_overlay.mediapipe_overlay_data import MediapipeOverlayData
from freemocap.core.types.type_overloads import TrackedPointNameString
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage
from skellyforge.data_models.trajectory_3d import Point3d

logger = logging.getLogger(__name__)

# Union type for all possible overlay data types
ObservationOverlayData = CharucoOverlayData | MediapipeOverlayData


class FrontendPayload(BaseModel):
    """Complete payload for frontend visualization"""
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=False
    )

    frame_number: int
    # Overlay data keyed by camera ID, supporting multiple detector types
    observation_overlays: dict[CameraIdString, ObservationOverlayData]
    tracked_points3d: dict[TrackedPointNameString, Point3d] = {}

    @classmethod
    def from_aggregation_output(
            cls,
            aggregation_output: AggregationNodeOutputMessage,
    ) -> "FrontendPayload":
        """Create frontend payload from aggregation node output."""
        observation_overlays: dict[CameraIdString, ObservationOverlayData] = {}

        charuco_overlay_data = getattr(aggregation_output, 'charuco_overlay_data', None)
        if charuco_overlay_data is not None:
            observation_overlays.update(charuco_overlay_data)

        mediapipe_overlay_data = getattr(aggregation_output, 'mediapipe_overlay_data', None)
        if mediapipe_overlay_data is not None:
            observation_overlays.update(mediapipe_overlay_data)

        return cls(
            frame_number=aggregation_output.frame_number,
            observation_overlays=observation_overlays,
            tracked_points3d=aggregation_output.tracked_points3d
        )

    def to_websocket_dict(self) -> dict:
        """
        Convert to dictionary suitable for JSON serialization over websocket.
        """
        payload = {
            "frame_number": self.frame_number,
            "observation_overlays": {
                camera_id: overlay.model_dump()
                for camera_id, overlay in self.observation_overlays.items()
            },
            "tracked_points3d": {
                name: point.model_dump()
                for name, point in self.tracked_points3d.items()
            }
        }

        return payload