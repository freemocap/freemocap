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


class FrontendPayload(BaseModel):
    """Complete payload for frontend visualization.

    Carries both charuco and mediapipe overlay data separately so both
    can be active simultaneously per camera.
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=False
    )

    frame_number: int
    charuco_overlays: dict[CameraIdString, CharucoOverlayData]
    mediapipe_overlays: dict[CameraIdString, MediapipeOverlayData]
    tracked_points3d: dict[TrackedPointNameString, Point3d]
    rigid_body_poses: dict[str, RigidBodyPose]

    @classmethod
    def from_aggregation_output(
            cls,
            aggregation_output: AggregationNodeOutputMessage,
    ) -> "FrontendPayload":
        """Create frontend payload from aggregation node output."""
        return cls(
            frame_number=aggregation_output.frame_number,
            charuco_overlays=aggregation_output.charuco_overlay_data,
            mediapipe_overlays=aggregation_output.mediapipe_overlay_data,
            tracked_points3d=aggregation_output.raw_keypoints,
            rigid_body_poses=aggregation_output.rigid_body_poses,
        )

    def to_websocket_dict(self) -> dict:
        """Convert to dictionary suitable for JSON serialization over websocket."""
        return {
            "frame_number": self.frame_number,
            "charuco_overlays": {
                camera_id: overlay.model_dump()
                for camera_id, overlay in self.charuco_overlays.items()
            },
            "mediapipe_overlays": {
                camera_id: overlay.model_dump()
                for camera_id, overlay in self.mediapipe_overlays.items()
            },
            "tracked_points3d": {
                name: point.model_dump()
                for name, point in self.tracked_points3d.items()
            },
            "rigid_body_poses": {
                bone_key: pose.model_dump()
                for bone_key, pose in self.rigid_body_poses.items()
            },
        }
