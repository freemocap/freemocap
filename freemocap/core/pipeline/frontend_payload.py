import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pubsub.pubsub_topics import AggregationNodeOutputMessage
from freemocap.core.tasks.calibration_task.calibration_helpers.calibration_display_helpers.charuco_3d_models import (
    MultiCameraCharuco3dData, 
    Charuco3dData, 
    Color
)
from freemocap.core.tasks.calibration_task.calibration_helpers.charuco_overlay_data import CharucoOverlayData

logger = logging.getLogger(__name__)


class FrontendPayload(BaseModel):
    """Complete payload for frontend visualization"""
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=False
    )
    
    frame_number: int
    charuco_overlays: dict[CameraIdString, CharucoOverlayData]
    charuco_3d_data: MultiCameraCharuco3dData | None = None
    
    @classmethod
    def from_aggregation_output(
        cls,
        aggregation_output: AggregationNodeOutputMessage,
    ) -> "FrontendPayload":
        """Create frontend payload from aggregation node output"""
        charuco_overlays = aggregation_output.charuco_overlay_data

        camera_3d_data: dict[CameraIdString, Charuco3dData] = {}

        for camera_id, camera_output in aggregation_output.camera_node_outputs.items():
            if camera_output and camera_output.charuco_observation:
                obs = camera_output.charuco_observation

                if obs.has_board_pose:
                    try:
                        camera_3d_data[camera_id] = Charuco3dData.from_charuco_observation(
                            camera_id=camera_id,
                            frame_number=aggregation_output.frame_number,
                            charuco_observation=obs,
                            coordinate_system="camera",
                            charuco_corner_radius=0.005,
                            aruco_corner_radius=0.003,
                            charuco_color=_get_camera_color(camera_id=camera_id,
                                                            camera_ids=aggregation_output.camera_ids,
                                                            element_type="charuco"),
                            aruco_color=_get_camera_color(camera_id=camera_id,
                                                            camera_ids=aggregation_output.camera_ids,
                                                          element_type="aruco"),
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to create 3D data for camera {camera_id}: {e}"
                        )
            
        # TODO: Add this after triangulation is implemented
        world_data = None

        charuco_3d_data = MultiCameraCharuco3dData(
            frame_number=aggregation_output.frame_number,
            camera_data=camera_3d_data,
            world_data=world_data
        )
        
        return cls(
            frame_number=aggregation_output.frame_number,
            charuco_overlays=charuco_overlays,
            charuco_3d_data=charuco_3d_data
        )
    
    def to_websocket_dict(self) -> dict:
        """
        Convert to dictionary suitable for JSON serialization over websocket.
        """
        payload = {
            "frame_number": self.frame_number,
            "charuco_overlays": {
                camera_id: overlay.model_dump() 
                for camera_id, overlay in self.charuco_overlays.items()
            }
        }
        
        if self.charuco_3d_data:
            # The MultiCameraCharuco3dData model serializes itself perfectly!
            payload["charuco_3d"] = self.charuco_3d_data.model_dump()
        
        return payload



def _get_camera_color(
        camera_id: CameraIdString,
        camera_ids: list[CameraIdString],
        element_type: Literal["charuco", "aruco"]
) -> Color:
    """
    Get consistent colors per camera for visualization based on camera order.

    Args:
        camera_id: The camera ID to get color for
        camera_ids: Ordered list of all camera IDs (determines color assignment)
        element_type: Whether this is for charuco corners or aruco markers

    Returns:
        Color object for the specified camera and element type
    """
    # Color palettes - will cycle through these if we have more cameras
    charuco_palette = [
        "#00FF00",  # Green
        "#0000FF",  # Blue
        "#FF0000",  # Red
        "#FFFF00",  # Yellow
        "#FF00FF",  # Magenta
        "#00FFFF",  # Cyan
        "#FF8800",  # Orange
        "#8800FF",  # Purple
    ]

    # Aruco markers use darker versions of the same hues
    aruco_palette = [
        "#00AA00",  # Dark Green
        "#0000AA",  # Dark Blue
        "#AA0000",  # Dark Red
        "#AAAA00",  # Dark Yellow
        "#AA00AA",  # Dark Magenta
        "#00AAAA",  # Dark Cyan
        "#AA5500",  # Dark Orange
        "#5500AA",  # Dark Purple
    ]

    # Get the camera index (determines which color to use)
    try:
        camera_index = camera_ids.index(camera_id)
    except ValueError:
        # Camera not in list - use default color
        default_hex = "#FFFFFF" if element_type == "charuco" else "#888888"
        return Color.from_hex(default_hex)

    # Select color from palette (with wrapping for > 8 cameras)
    palette = charuco_palette if element_type == "charuco" else aruco_palette
    color_hex = palette[camera_index % len(palette)]

    return Color.from_hex(color_hex)