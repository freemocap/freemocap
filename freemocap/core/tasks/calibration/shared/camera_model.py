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
