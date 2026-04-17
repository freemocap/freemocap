import logging

import msgspec
from freemocap.core.viz.image_overlay.skeleton_overlay_data import SkeletonOverlayData
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.types.type_overloads import CameraIdString, CameraGroupIdString, MultiframeTimestampFloat
from skellyforge.data_models.trajectory_3d import Point3d

from freemocap.core.tasks.mocap.skeleton_dewiggler.dewiggling_methods.rigid_body_estimator import RigidBodyPose
from freemocap.core.types.type_overloads import TrackedPointNameString, PipelineIdString, FrameNumberInt
from freemocap.core.viz.image_overlay.charuco_overlay_data import CharucoOverlayData
# from freemocap.core.viz.image_overlay.mediapipe_overlay_data import MediapipeOverlayData
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage

logger = logging.getLogger(__name__)

# freemocap/core/viz/frontend_image_packet.py
from dataclasses import dataclass


class FrontendPayload(msgspec.Struct):
    """Complete payload for frontend visualization.

    Carries both charuco and mediapipe overlay data separately so both
    can be active simultaneously per camera.
    """

    frame_number: FrameNumberInt
    camera_group_id: CameraGroupIdString
    message_type: str = "frontend_payload"
    pipeline_id: PipelineIdString | None = None
    charuco_overlays: dict[CameraIdString, CharucoOverlayData] | None = None
    skeleton_overlays: dict[CameraIdString, SkeletonOverlayData] | None = None
    keypoints_raw: dict[TrackedPointNameString, Point3d] | None = None
    keypoints_filtered: dict[TrackedPointNameString, Point3d] | None = None
    rigid_body_poses: dict[str, RigidBodyPose] | None = None

    @classmethod
    def from_aggregation_output(
            cls,
            aggregation_output: AggregationNodeOutputMessage,
    ) -> "FrontendPayload":
        """Create frontend payload from aggregation node output."""
        return cls(
            frame_number=aggregation_output.frame_number,
            camera_group_id=aggregation_output.camera_group_id,
            pipeline_id=aggregation_output.pipeline_id,
            charuco_overlays=aggregation_output.charuco_overlay_data,
            skeleton_overlays=aggregation_output.skeleton_overlay_data,
            keypoints_raw=aggregation_output.keypoints_raw,
            keypoints_filtered=aggregation_output.keypoints_filtered,
            rigid_body_poses=aggregation_output.rigid_body_poses,
        )

@dataclass(slots=True, frozen=True)
class FrontendImagePacket:
    images_bytearray: bytearray
    multiframe_timestamp: MultiframeTimestampFloat
    frontend_payload: FrontendPayload

    @property
    def frame_number(self) -> FrameNumberInt:
        return FrameNumberInt(self.frontend_payload.frame_number)

    @property
    def camera_group_id(self) -> CameraGroupIdString:
        return self.frontend_payload.camera_group_id
