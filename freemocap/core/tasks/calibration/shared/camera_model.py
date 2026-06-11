import numpy as np
from freemocap.core.tasks.calibration.shared.camera_intrinsics import CameraIntrinsics
from freemocap.core.tasks.calibration.shared.camera_extrinsics import CameraExtrinsics
from freemocap.utilities.toml_mixin import TomlMixin
from numpy._typing import NDArray
from pydantic import BaseModel, ConfigDict
from skellycam.core.types.type_overloads import CameraIdString, CameraIndexInt


class CameraModel(BaseModel, TomlMixin):
    """Complete camera model: intrinsics + extrinsics + metadata."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    id: CameraIdString
    index: CameraIndexInt
    image_size: tuple[int, int]  # (width, height)
    intrinsics: CameraIntrinsics
    extrinsics: CameraExtrinsics
    world_position: NDArray[np.float64] = np.zeros(3, dtype=np.float64)
    world_orientation: NDArray[np.float64] = np.eye(3, dtype=np.float64)

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

