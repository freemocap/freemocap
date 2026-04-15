import msgspec
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation


class CharucoPointModel(msgspec.Struct):
    """A single detected Charuco corner point."""
    id: int
    x: float
    y: float


class ArucoMarkerModel(msgspec.Struct):
    """A single detected ArUco marker with 4 corners."""
    id: int
    corners: list[tuple[float, float]]


class CharucoMetadataModel(msgspec.Struct):
    """Metadata about the charuco detection."""
    n_charuco_detected: int
    n_charuco_total: int
    n_aruco_detected: int
    n_aruco_total: int
    has_pose: bool
    image_width: int
    image_height: int


class CharucoOverlayData(msgspec.Struct):
    """Complete message for transmitting charuco observation over websocket."""
    camera_id: str
    frame_number: int
    metadata: CharucoMetadataModel
    message_type: str = "charuco_overlay"
    charuco_corners: list[CharucoPointModel] = []
    aruco_markers: list[ArucoMarkerModel] = []

    @classmethod
    def from_charuco_observation(
            cls,
            *,
            camera_id: CameraIdString,
            observation: CharucoObservation,
            scale: float = .5, ):
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
                        x=float(corner_coords[0]) * scale,
                        y=float(corner_coords[1]) * scale,
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
                            (float(marker_corners[i][0] * scale),
                             float(marker_corners[i][1] * scale))
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
        return cls(
            camera_id=camera_id,
            frame_number=observation.frame_number,
            charuco_corners=charuco_corners,
            aruco_markers=aruco_markers,
            metadata=metadata,
        )
