import logging

from pydantic import BaseModel, ConfigDict
from skellycam.core.types.type_overloads import CameraIdString
from skellyforge.data_models.trajectory_3d import Point3d

from freemocap.core.tasks.mocap.skeleton_dewiggler.dewiggling_methods.rigid_body_estimator import RigidBodyPose
from freemocap.core.types.type_overloads import TrackedPointNameString
from freemocap.core.viz.image_overlay.charuco_overlay_data import CharucoOverlayData
from freemocap.core.viz.image_overlay.mediapipe_overlay_data import MediapipeOverlayData
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage

logger = logging.getLogger(__name__)

# freemocap/core/viz/frontend_image_packet.py
from dataclasses import dataclass




class FrontendPayload(BaseModel):
    """Complete payload for frontend visualization.

    Carries both charuco and mediapipe overlay data separately so both
    can be active simultaneously per camera.
    """

    frame_number: int
    charuco_overlays: dict[CameraIdString, CharucoOverlayData]
    skeleton_overlays: dict[CameraIdString, MediapipeOverlayData]
    keypoints_raw: dict[TrackedPointNameString, Point3d]
    keypoints_filtered: dict[TrackedPointNameString, Point3d]
    rigid_body_poses: dict[str, RigidBodyPose]
    message_type: str = "frontend_payload"

    @classmethod
    def from_aggregation_output(
            cls,
            aggregation_output: AggregationNodeOutputMessage,
    ) -> "FrontendPayload":
        """Create frontend payload from aggregation node output."""
        return cls(
            frame_number=aggregation_output.frame_number,
            charuco_overlays=aggregation_output.charuco_overlay_data,
            skeleton_overlays=aggregation_output.mediapipe_overlay_data,
            keypoints_raw=aggregation_output.keypoints_raw,
            keypoints_filtered=aggregation_output.keypoints_filtered,
            rigid_body_poses=aggregation_output.rigid_body_poses,
        )

@dataclass(slots=True, frozen=True)
class FrontendImagePacket:
    """
    Unified output type for all frontend image relay paths.

    `frontend_payload` is None in camera-only mode (no active pipeline).
    `frame_number` is always populated so the relay can track acknowledgment
    without any isinstance checks.
    """
    image_bytes: bytes | None
    frame_number: int
    frontend_payload: FrontendPayload | None  # None = camera-only mode
