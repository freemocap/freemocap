import logging

import msgspec
import numpy as np
from freemocap.core.viz.image_overlay.skeleton_overlay_data import SkeletonOverlayData
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.types.type_overloads import CameraIdString, CameraGroupIdString, MultiframeTimestampFloat
from skellyforge.data_models.trajectory_3d import Point3d

from freemocap.core.types.type_overloads import TrackedPointNameString, PipelineIdString, FrameNumberInt
from freemocap.core.viz.image_overlay.charuco_overlay_data import CharucoOverlayData
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage

logger = logging.getLogger(__name__)

# freemocap/core/viz/frontend_image_packet.py
from dataclasses import dataclass


class FrontendPayload(msgspec.Struct):
    """Complete payload for frontend visualization.

    Carries charuco/skeleton overlay data, triangulated keypoints, and
    the FABRIK-fitted canonical skeleton.
    """

    frame_number: FrameNumberInt
    camera_group_id: CameraGroupIdString
    message_type: str = "frontend_payload"
    pipeline_id: PipelineIdString | None = None
    charuco_overlays: dict[CameraIdString, CharucoOverlayData] | None = None
    skeleton_overlays: dict[CameraIdString, SkeletonOverlayData] | None = None
    keypoints: dict[TrackedPointNameString, Point3d] | None = None
    center_of_mass: Point3d | None = None
    xcom: Point3d | None = None
    skeleton: dict[TrackedPointNameString, Point3d] | None = None

    @classmethod
    def from_aggregation_output(
            cls,
            aggregation_output: AggregationNodeOutputMessage,
    ) -> "FrontendPayload":
        """Create frontend payload from aggregation node output."""
        com = aggregation_output.center_of_mass_result
        com_point = None
        if com is not None and not np.any(np.isnan(com.total_body_com)):
            com_arr = com.total_body_com
            com_point = Point3d(
                x=float(com_arr[0]),
                y=float(com_arr[1]),
                z=float(com_arr[2]),
            )

        return cls(
            frame_number=aggregation_output.frame_number,
            camera_group_id=aggregation_output.camera_group_id,
            pipeline_id=aggregation_output.pipeline_id,
            charuco_overlays=aggregation_output.charuco_overlay_data,
            skeleton_overlays=aggregation_output.skeleton_overlay_data,
            keypoints=aggregation_output.keypoints,
            center_of_mass=com_point,
            xcom=aggregation_output.xcom,
            skeleton=(
                {
                    name: Point3d(x=float(arr[0]), y=float(arr[1]), z=float(arr[2]))
                    for name, arr in aggregation_output.skeleton.items()
                }
                if aggregation_output.skeleton
                else None
            ),
        )

@dataclass(slots=True, frozen=True)
class FrontendImagePacket:
    images_bytearray: bytearray
    multiframe_timestamp: MultiframeTimestampFloat
    frontend_payload: FrontendPayload
    # Optional binary keypoints message. Built when FREEMOCAP_BINARY_KEYPOINTS=1.
    # Format: see freemocap.api.websocket.binary_keypoints_protocol.
    keypoints_binary_payload: bytearray | None = None

    @property
    def frame_number(self) -> FrameNumberInt:
        return FrameNumberInt(self.frontend_payload.frame_number)

    @property
    def camera_group_id(self) -> CameraGroupIdString:
        return self.frontend_payload.camera_group_id
