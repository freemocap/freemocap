"""
Serialize CharucoObservation to JSON format for websocket transmission using Pydantic models.
"""

import numpy as np
from pydantic import BaseModel, Field
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation
from skellycam.core.types.type_overloads import CameraIdString
from typing import Literal


class CharucoPointModel(BaseModel):
    """A single detected Charuco corner point."""
    id: int = Field(description="Charuco corner ID")
    x: float = Field(description="X coordinate in image space")
    y: float = Field(description="Y coordinate in image space")


class ArucoMarkerModel(BaseModel):
    """A single detected ArUco marker with 4 corners."""
    id: int = Field(description="ArUco marker ID")
    corners: list[tuple[float, float]] = Field(
        description="Four corners of the marker [(x,y), (x,y), (x,y), (x,y)]",
        min_length=4,
        max_length=4
    )


class CharucoMetadataModel(BaseModel):
    """Metadata about the charuco detection."""
    n_charuco_detected: int = Field(description="Number of Charuco corners detected")
    n_charuco_total: int = Field(description="Total number of Charuco corners on board")
    n_aruco_detected: int = Field(description="Number of ArUco markers detected")
    n_aruco_total: int = Field(description="Total number of ArUco markers on board")
    has_pose: bool = Field(description="Whether board pose was successfully estimated")
    image_width: int = Field(description="Width of the image in pixels")
    image_height: int = Field(description="Height of the image in pixels")


class CharucoObservationMessage(BaseModel):
    """Complete message for transmitting charuco observation over websocket."""
    message_type: Literal["charuco_observation"] = "charuco_observation"
    camera_id: CameraIdString = Field(description="ID of the camera that produced this observation")
    frame_number: int = Field(description="Frame number of this observation")
    charuco_corners: list[CharucoPointModel] = Field(
        default_factory=list,
        description="List of detected Charuco corner points"
    )
    aruco_markers: list[ArucoMarkerModel] = Field(
        default_factory=list,
        description="List of detected ArUco markers"
    )
    metadata: CharucoMetadataModel = Field(description="Detection metadata and statistics")


def charuco_observation_to_message(
    *,
    camera_id: CameraIdString,
    observation: CharucoObservation,
) -> CharucoObservationMessage:
    """
    Convert CharucoObservation to Pydantic message model for websocket transmission.
    
    Args:
        camera_id: ID of the camera that produced this observation
        observation: The CharucoObservation to serialize
        
    Returns:
        CharucoObservationMessage ready for JSON serialization
    """
    
    # Build Charuco corner models
    charuco_corners: list[CharucoPointModel] = []
    if not observation.charuco_empty:
        for corner_id, corner_coords in observation.charuco_corners_dict.items():
            charuco_corners.append(
                CharucoPointModel(
                    id=int(corner_id),
                    x=float(corner_coords[0]),
                    y=float(corner_coords[1]),
                )
            )
    
    # Build ArUco marker models
    aruco_markers: list[ArucoMarkerModel] = []
    if not observation.aruco_empty:
        for marker_id, marker_corners in observation.aruco_corners_dict.items():
            aruco_markers.append(
                ArucoMarkerModel(
                    id=int(marker_id),
                    corners=[
                        (float(marker_corners[i][0]), float(marker_corners[i][1]))
                        for i in range(4)
                    ],
                )
            )
    
    # Build metadata model
    metadata = CharucoMetadataModel(
        n_charuco_detected=0 if observation.charuco_empty else len(observation.detected_charuco_corner_ids),
        n_charuco_total=len(observation.all_charuco_ids),
        n_aruco_detected=0 if observation.aruco_empty else len(observation.detected_aruco_marker_ids),
        n_aruco_total=len(observation.all_aruco_ids),
        has_pose=observation.charuco_board_translation_vector is not None,
        image_width=observation.image_size[0],
        image_height=observation.image_size[1],
    )
    
    # Build complete message
    return CharucoObservationMessage(
        camera_id=camera_id,
        frame_number=observation.frame_number,
        charuco_corners=charuco_corners,
        aruco_markers=aruco_markers,
        metadata=metadata,
    )


def serialize_charuco_observation(
    *,
    camera_id: CameraIdString,
    observation: CharucoObservation,
) -> dict[str, object]:
    """
    Convert CharucoObservation to JSON-serializable dict for websocket transmission.
    
    Args:
        camera_id: ID of the camera that produced this observation
        observation: The CharucoObservation to serialize
        
    Returns:
        Dictionary ready for JSON serialization via websocket.send_json()
    """
    message = charuco_observation_to_message(
        camera_id=camera_id,
        observation=observation,
    )
    return message.model_dump()
