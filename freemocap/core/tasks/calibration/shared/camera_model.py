import numpy as np
from skellyforge.core.math.geometry.rotation_quaternion import RotationQuaternion
from skellyforge.core.math.geometry.transform_math import Transform
from typing import Annotated
from freemocap.core.tasks.calibration.shared.camera_intrinsics import CameraIntrinsics
from freemocap.core.tasks.calibration.shared.camera_extrinsics import CameraExtrinsics
from freemocap.utilities.toml_mixin import TomlMixin
from numpy._typing import NDArray
from pydantic import BaseModel, ConfigDict, field_validator, field_serializer, WithJsonSchema
from skellycam.core.types.type_overloads import CameraIdString, CameraIndexInt


class CameraModel(BaseModel, TomlMixin):
    """Complete camera model: intrinsics + extrinsics + metadata."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    id: CameraIdString
    index: CameraIndexInt
    image_size: tuple[int, int]  # (width, height)
    intrinsics: CameraIntrinsics
    extrinsics: CameraExtrinsics
    world_position: Annotated[NDArray[np.float64], WithJsonSchema({"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3})] = np.zeros(3, dtype=np.float64)
    world_orientation: Annotated[NDArray[np.float64], WithJsonSchema({"type": "array", "items": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}, "minItems": 3, "maxItems": 3})] = np.eye(3, dtype=np.float64)

    @field_validator("world_position", mode="before")
    @classmethod
    def validate_world_position(cls, value: NDArray[np.float64] | list[float]) -> NDArray[np.float64]:
        array = np.asarray(value, dtype=np.float64)
        if array.shape != (3,) or not np.isfinite(array).all():
            raise ValueError("Camera world position requires three finite coordinates")
        return array

    @field_validator("world_orientation", mode="before")
    @classmethod
    def validate_world_orientation(cls, value: NDArray[np.float64] | list[list[float]]) -> NDArray[np.float64]:
        array = np.asarray(value, dtype=np.float64)
        if array.shape != (3, 3) or not np.isfinite(array).all():
            raise ValueError("Camera world orientation requires a finite 3x3 matrix")
        return array

    @field_serializer("world_position", when_used="json")
    def serialize_world_position(self, value: NDArray[np.float64]) -> list[float]:
        return value.tolist()

    @field_serializer("world_orientation", when_used="json")
    def serialize_world_orientation(self, value: NDArray[np.float64]) -> list[list[float]]:
        return value.tolist()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, CameraModel) and self.model_dump(mode="json") == other.model_dump(mode="json")

    def in_world_frame(self, *, transform: Transform) -> "CameraModel":
        """Express this camera in X' = Q X + b without changing its projection.

        The transform must use the same coordinates and length unit as the extrinsics.
        Camera-local coordinates and intrinsics are unchanged; all world-pose fields
        are derived from the transformed extrinsics.
        """
        rotation = self.extrinsics.rotation_matrix @ transform.rotation.to_rotation_matrix().T
        extrinsics = CameraExtrinsics(
            quaternion_wxyz=RotationQuaternion.from_rotation_matrix(matrix=rotation).as_array(),
            translation=self.extrinsics.translation - rotation @ transform.translation.array,
        )
        result = self.model_copy(deep=True)
        result.extrinsics = extrinsics
        result.world_position = extrinsics.world_position
        result.world_orientation = extrinsics.world_orientation
        return result

    @property
    def projection_matrix(self) -> NDArray[np.float64]:
        """Full 3x4 projection matrix P = K @ [R|t]."""
        K = self.intrinsics.to_camera_matrix()
        R = self.extrinsics.rotation_matrix
        t = self.extrinsics.translation
        Rt = np.zeros((3, 4), dtype=np.float64)
        Rt[:, :3] = R
        Rt[:, 3] = t
        return K @ Rt

    def __str__(self) -> str:
        width, height = self.image_size
        intrinsics = self.intrinsics
        extrinsics = self.extrinsics
        world_position_meters = self.world_position / 1000.0

        lines = [
            f"CameraModel:",
            f"  id                  = {self.id}",
            f"  index               = {self.index}",
            f"  image_size          = {width} x {height} pixels",
            f"  intrinsics:",
            f"    fx = {intrinsics.fx:.6f}",
            f"    fy = {intrinsics.fy:.6f}",
            f"    cx = {intrinsics.cx:.6f}",
            f"    cy = {intrinsics.cy:.6f}",
            f"    k1 = {intrinsics.k1:.6f}",
            f"    k2 = {intrinsics.k2:.6f}",
            f"    p1 = {intrinsics.p1:.6f}",
            f"    p2 = {intrinsics.p2:.6f}",
            f"  extrinsics:",
            f"    quaternion_wxyz    = [{extrinsics.quaternion_wxyz[0]:.6f}, {extrinsics.quaternion_wxyz[1]:.6f}, {extrinsics.quaternion_wxyz[2]:.6f}, {extrinsics.quaternion_wxyz[3]:.6f}]",
            f"    translation (mm)   = [{extrinsics.translation[0]:.6f}, {extrinsics.translation[1]:.6f}, {extrinsics.translation[2]:.6f}]",
            f"    rotation_matrix (R, world→camera):",
            f"      [{extrinsics.rotation_matrix[0,0]:.6f}  {extrinsics.rotation_matrix[0,1]:.6f}  {extrinsics.rotation_matrix[0,2]:.6f}]",
            f"      [{extrinsics.rotation_matrix[1,0]:.6f}  {extrinsics.rotation_matrix[1,1]:.6f}  {extrinsics.rotation_matrix[1,2]:.6f}]",
            f"      [{extrinsics.rotation_matrix[2,0]:.6f}  {extrinsics.rotation_matrix[2,1]:.6f}  {extrinsics.rotation_matrix[2,2]:.6f}]",
            f"  world_position (mm)  = [{self.world_position[0]:.6f}, {self.world_position[1]:.6f}, {self.world_position[2]:.6f}]",
            f"  world_position (m)   = [{world_position_meters[0]:.6f}, {world_position_meters[1]:.6f}, {world_position_meters[2]:.6f}]",
            f"  world_orientation (camera→world):",
            f"    [{self.world_orientation[0,0]:.6f}  {self.world_orientation[0,1]:.6f}  {self.world_orientation[0,2]:.6f}]",
            f"    [{self.world_orientation[1,0]:.6f}  {self.world_orientation[1,1]:.6f}  {self.world_orientation[1,2]:.6f}]",
            f"    [{self.world_orientation[2,0]:.6f}  {self.world_orientation[2,1]:.6f}  {self.world_orientation[2,2]:.6f}]",
        ]
        return "\n".join(lines)

