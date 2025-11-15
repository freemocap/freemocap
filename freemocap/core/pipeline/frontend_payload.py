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
    # Now supports multiple observation types
    observation_overlays: dict[CameraIdString, ObservationOverlayData]
    tracked_points3d: dict[TrackedPointNameString, Point3d] = {}

    @classmethod
    def from_aggregation_output(
            cls,
            aggregation_output: AggregationNodeOutputMessage,
    ) -> "FrontendPayload":
        """Create frontend payload from aggregation node output"""

        # Combine all observation types into single dict
        observation_overlays: dict[CameraIdString, ObservationOverlayData] = {}

        # Add charuco overlays if present
        if hasattr(aggregation_output, 'charuco_overlay_data'):
            observation_overlays.update(aggregation_output.charuco_overlay_data)

        # Add mediapipe overlays if present
        if hasattr(aggregation_output, 'mediapipe_overlay_data'):
            observation_overlays.update(aggregation_output.mediapipe_overlay_data)

        # Add other overlay types as they're implemented
        # if hasattr(aggregation_output, 'rtmpose_overlay_data'):
        #     observation_overlays.update(aggregation_output.rtmpose_overlay_data)

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