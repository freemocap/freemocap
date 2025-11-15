from typing import Literal, Any

import numpy as np
from numpydantic import NDArray, Shape
from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_serializer
from skellycam.core.types.type_overloads import CameraIdString


class Color(BaseModel):
    """RGB color with alpha channel (0-1 range for Three.js compatibility)"""
    model_config = ConfigDict(frozen=True)

    r: float = Field(ge=0.0, le=1.0)
    g: float = Field(ge=0.0, le=1.0)
    b: float = Field(ge=0.0, le=1.0)
    a: float = Field(default=1.0, ge=0.0, le=1.0)

    @classmethod
    def from_hex(cls, hex_color: str) -> "Color":
        """Create color from hex string like '#FF5733' or 'FF5733'"""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            return cls(r=r / 255.0, g=g / 255.0, b=b / 255.0)
        raise ValueError(f"Invalid hex color: {hex_color}")

    @classmethod
    def from_rgb_255(cls, r: int, g: int, b: int, a: float = 1.0) -> "Color":
        """Create color from 0-255 RGB values"""
        return cls(r=r / 255.0, g=g / 255.0, b=b / 255.0, a=a)

    def to_hex(self) -> str:
        """Convert to hex string for Three.js"""
        r = int(self.r * 255)
        g = int(self.g * 255)
        b = int(self.b * 255)
        return f"#{r:02x}{g:02x}{b:02x}"

    @model_serializer
    def _serialize(self) -> str:
        """Serialize directly to hex string"""
        return self.to_hex()


class Point3d(BaseModel):
    """3D point in space - serializes to [x, y, z] array"""
    model_config = ConfigDict(frozen=True)

    x: float
    y: float
    z: float

    @classmethod
    def from_array(cls, array: np.ndarray) -> "Point3d":
        """Create from numpy array [x, y, z]"""
        if array.shape != (3,):
            raise ValueError(f"Expected array of shape (3,), got {array.shape}")
        return cls(x=float(array[0]), y=float(array[1]), z=float(array[2]))

    def to_array(self) -> np.ndarray:
        """Convert to numpy array"""
        return np.array([self.x, self.y, self.z], dtype=np.float32)

    @model_serializer
    def _serialize(self) -> list[float]:
        """Serialize directly to [x, y, z] list"""
        return [self.x, self.y, self.z]


class Sphere3d(BaseModel):
    """Sphere for rendering in Three.js"""
    model_config = ConfigDict(frozen=True)

    id: str
    position: Point3d
    radius: float = Field(gt=0.0)
    color: Color
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    label: str | None = None


class Line3d(BaseModel):
    """Line connecting two points for rendering in Three.js"""
    model_config = ConfigDict(frozen=True)

    id: str
    start: Point3d
    end: Point3d
    color: Color
    thickness: float = Field(default=1.0, gt=0.0)
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    dashed: bool = False


class CoordinateFrame3d(BaseModel):
    """Coordinate frame showing X, Y, Z axes"""
    model_config = ConfigDict(frozen=True)

    id: str
    origin: Point3d
    x_axis: Point3d
    y_axis: Point3d
    z_axis: Point3d
    scale: float = Field(default=1.0, gt=0.0)
    label: str | None = None


class BoardPose3d(BaseModel):
    """Pose of the Charuco board in 3D space"""
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        frozen=True
    )

    rotation_vector: NDArray[Shape["3"], np.float32]
    translation_vector: NDArray[Shape["3"], np.float32]
    coordinate_frame: CoordinateFrame3d | None = None

    @field_serializer('rotation_vector', 'translation_vector')
    def _serialize_vectors(self, value: np.ndarray) -> list[float]:
        """Serialize numpy arrays to lists"""
        return value.tolist()

    @classmethod
    def create_with_frame(
            cls,
            rotation_vector: np.ndarray,
            translation_vector: np.ndarray,
            frame_id: str,
            frame_scale: float = 0.1,
            label: str | None = None
    ) -> "BoardPose3d":
        """Create board pose with coordinate frame for visualization"""
        import cv2

        rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
        origin = Point3d.from_array(translation_vector)

        x_end = origin.to_array() + rotation_matrix[:, 0] * frame_scale
        y_end = origin.to_array() + rotation_matrix[:, 1] * frame_scale
        z_end = origin.to_array() + rotation_matrix[:, 2] * frame_scale

        coordinate_frame = CoordinateFrame3d(
            id=frame_id,
            origin=origin,
            x_axis=Point3d.from_array(x_end),
            y_axis=Point3d.from_array(y_end),
            z_axis=Point3d.from_array(z_end),
            scale=frame_scale,
            label=label
        )

        return cls(
            rotation_vector=rotation_vector,
            translation_vector=translation_vector,
            coordinate_frame=coordinate_frame
        )


class ArucoMarker3d(BaseModel):
    """3D representation of an ArUco marker with 4 corner spheres"""
    model_config = ConfigDict(frozen=True)

    marker_id: int
    corner_spheres: list[Sphere3d] = Field(min_length=4, max_length=4)
    edge_lines: list[Line3d] = Field(min_length=4, max_length=4)
    center_sphere: Sphere3d | None = None


class Charuco3dData(BaseModel):
    """Complete 3D visualization data for Charuco board detection"""
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        frozen=True
    )

    camera_id: CameraIdString
    frame_number: int
    coordinate_system: Literal["camera", "world"]

    charuco_corner_spheres: dict[int, Sphere3d]
    charuco_corner_connections: list[Line3d]
    aruco_markers: dict[int, ArucoMarker3d]
    board_pose: BoardPose3d | None = None

    all_corner_count: int
    detected_corner_count: int
    detection_quality: float = Field(ge=0.0, le=1.0)

    @classmethod
    def from_charuco_observation(
            cls,
            camera_id: CameraIdString,
            frame_number: int,
            charuco_observation: "CharucoObservation",  # type: ignore
            coordinate_system: Literal["camera", "world"] = "camera",
            charuco_corner_radius: float = 0.005,
            aruco_corner_radius: float = 0.003,
            charuco_color: Color | None = None,
            aruco_color: Color | None = None,
            connection_color: Color | None = None,
    ) -> "Charuco3dData":
        """Create visualization data from CharucoObservation"""

        if charuco_color is None:
            charuco_color = Color.from_hex("#00FF00")
        if aruco_color is None:
            aruco_color = Color.from_hex("#FF0000")
        if connection_color is None:
            connection_color = Color.from_hex("#FFFFFF")

        if coordinate_system == "camera":
            if charuco_observation.detected_charuco_corners_in_camera_coordinates is None:
                raise ValueError(
                    "Camera coordinates not computed. Call compute_board_pose_and_camera_coordinates first.")
            corner_coords = charuco_observation.detected_charuco_corners_in_camera_coordinates
            aruco_coords = charuco_observation.detected_aruco_markers_in_camera_coordinates
        else:
            corner_coords = charuco_observation.detected_charuco_corners_in_object_coordinates
            aruco_coords = None

        charuco_corner_spheres: dict[int, Sphere3d] = {}
        if (corner_coords is not None and
                charuco_observation.detected_charuco_corner_ids is not None):
            for i, corner_id in enumerate(charuco_observation.detected_charuco_corner_ids):
                corner_id_int = int(corner_id)
                position = Point3d.from_array(corner_coords[i])
                charuco_corner_spheres[corner_id_int] = Sphere3d(
                    id=f"charuco_corner_{corner_id_int}",
                    position=position,
                    radius=charuco_corner_radius,
                    color=charuco_color,
                    label=f"C{corner_id_int}"
                )

        charuco_corner_connections: list[Line3d] = []

        aruco_markers: dict[int, ArucoMarker3d] = {}
        if (aruco_coords is not None and
                charuco_observation.detected_aruco_marker_ids is not None):
            for i, marker_id in enumerate(charuco_observation.detected_aruco_marker_ids):
                marker_id_int = int(marker_id)
                marker_corners = aruco_coords[i]

                corner_spheres = [
                    Sphere3d(
                        id=f"aruco_{marker_id_int}_corner_{j}",
                        position=Point3d.from_array(marker_corners[j]),
                        radius=aruco_corner_radius,
                        color=aruco_color,
                        label=None
                    )
                    for j in range(4)
                ]

                edge_lines = [
                    Line3d(
                        id=f"aruco_{marker_id_int}_edge_{j}",
                        start=Point3d.from_array(marker_corners[j]),
                        end=Point3d.from_array(marker_corners[(j + 1) % 4]),
                        color=aruco_color,
                        thickness=2.0
                    )
                    for j in range(4)
                ]

                center = np.mean(marker_corners, axis=0)
                center_sphere = Sphere3d(
                    id=f"aruco_{marker_id_int}_center",
                    position=Point3d.from_array(center),
                    radius=aruco_corner_radius * 1.5,
                    color=aruco_color,
                    opacity=0.5,
                    label=f"A{marker_id_int}"
                )

                aruco_markers[marker_id_int] = ArucoMarker3d(
                    marker_id=marker_id_int,
                    corner_spheres=corner_spheres,
                    edge_lines=edge_lines,
                    center_sphere=center_sphere
                )

        board_pose = None
        if charuco_observation.has_board_pose:
            board_pose = BoardPose3d.create_with_frame(
                rotation_vector=charuco_observation.charuco_board_rotation_vector,
                translation_vector=charuco_observation.charuco_board_translation_vector,
                frame_id=f"board_frame_{camera_id}",
                frame_scale=0.1,
                label=f"Board ({camera_id})"
            )

        all_corner_count = len(charuco_observation.all_charuco_ids)
        detected_corner_count = len(charuco_corner_spheres)
        detection_quality = detected_corner_count / all_corner_count if all_corner_count > 0 else 0.0

        return cls(
            camera_id=camera_id,
            frame_number=frame_number,
            coordinate_system=coordinate_system,
            charuco_corner_spheres=charuco_corner_spheres,
            charuco_corner_connections=charuco_corner_connections,
            aruco_markers=aruco_markers,
            board_pose=board_pose,
            all_corner_count=all_corner_count,
            detected_corner_count=detected_corner_count,
            detection_quality=detection_quality
        )


class MultiCameraCharuco3dData(BaseModel):
    """Aggregated 3D data from multiple cameras"""
    model_config = ConfigDict(frozen=True)

    frame_number: int
    camera_data: dict[CameraIdString, Charuco3dData]
    world_data: Charuco3dData | None = None

    def get_all_spheres(self) -> list[Sphere3d]:
        """Get all spheres across all cameras for batch rendering"""
        spheres = []
        for cam_data in self.camera_data.values():
            spheres.extend(cam_data.charuco_corner_spheres.values())
            for marker in cam_data.aruco_markers.values():
                spheres.extend(marker.corner_spheres)
                if marker.center_sphere:
                    spheres.append(marker.center_sphere)
        if self.world_data:
            spheres.extend(self.world_data.charuco_corner_spheres.values())
        return spheres

    def get_all_lines(self) -> list[Line3d]:
        """Get all lines across all cameras for batch rendering"""
        lines = []
        for cam_data in self.camera_data.values():
            lines.extend(cam_data.charuco_corner_connections)
            for marker in cam_data.aruco_markers.values():
                lines.extend(marker.edge_lines)
        if self.world_data:
            lines.extend(self.world_data.charuco_corner_connections)
        return lines

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        """Custom serialization to flatten structure for efficient websocket transmission"""
        return {
            "frame_number": self.frame_number,
            "cameras": {
                camera_id: cam_data.model_dump()
                for camera_id, cam_data in self.camera_data.items()
            },
            "all_spheres": [sphere.model_dump() for sphere in self.get_all_spheres()],
            "all_lines": [line.model_dump() for line in self.get_all_lines()],
            "world": self.world_data.model_dump() if self.world_data else None
        }
