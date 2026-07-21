import msgspec
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.core.data_primitives.observation import Observation


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
    def from_observation(
            cls,
            *,
            camera_id: CameraIdString,
            observation: Observation,
            scale: float = 1.0,
    ) -> "CharucoOverlayData":
        stage = observation.stages.get("charuco")
        if stage is None or stage.keypoints is None:
            return cls(
                camera_id=camera_id,
                frame_number=observation.frame_number,
                charuco_corners=[],
                aruco_markers=[],
                metadata=CharucoMetadataModel(
                    n_charuco_detected=0, n_charuco_total=0,
                    n_aruco_detected=0, n_aruco_total=0,
                    image_width=observation.image_size[1],
                    image_height=observation.image_size[0],
                ),
            )

        kpts = stage.keypoints
        charuco_corners: list[CharucoPointModel] = []
        # marker_id -> list of 4 corner coords, indexed by j
        aruco_corner_map: dict[int, list[tuple[float, float] | None]] = {}
        n_charuco_total = 0
        n_aruco_markers = 0

        for i, name in enumerate(kpts.names):
            if name.startswith("CharucoCorner-"):
                corner_id = int(name.split("-")[1])
                n_charuco_total += 1
                if kpts.visibility[i] > 0.0:
                    charuco_corners.append(
                        CharucoPointModel(
                            id=corner_id,
                            x=float(kpts.xyz[i, 0]) * scale,
                            y=float(kpts.xyz[i, 1]) * scale,
                        )
                    )
            elif name.startswith("ArucoMarkerCorner-"):
                parts = name.split("-")
                marker_id = int(parts[1])
                j = int(parts[2])
                if marker_id not in aruco_corner_map:
                    aruco_corner_map[marker_id] = [None] * 4
                    n_aruco_markers += 1
                if kpts.visibility[i] > 0.0:
                    aruco_corner_map[marker_id][j] = (
                        float(kpts.xyz[i, 0]) * scale,
                        float(kpts.xyz[i, 1]) * scale,
                    )

        aruco_markers: list[ArucoMarkerModel] = []
        n_aruco_detected = 0
        for marker_id, corners in aruco_corner_map.items():
            filled = [corner for corner in corners if corner is not None]
            if len(filled) == 4:
                aruco_markers.append(
                    ArucoMarkerModel(id=marker_id, corners=filled)
                )
                n_aruco_detected += 1

        return cls(
            camera_id=camera_id,
            frame_number=observation.frame_number,
            charuco_corners=charuco_corners,
            aruco_markers=aruco_markers,
            metadata=CharucoMetadataModel(
                n_charuco_detected=len(charuco_corners),
                n_charuco_total=n_charuco_total,
                n_aruco_detected=n_aruco_detected,
                n_aruco_total=n_aruco_markers,
                image_width=observation.image_size[1],
                image_height=observation.image_size[0],
            ),
        )
