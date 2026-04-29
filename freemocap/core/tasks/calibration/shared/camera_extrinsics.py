import cv2
import numpy as np
from freemocap.utilities.toml_mixin import TomlMixin
from numpy._typing import NDArray
from pydantic import BaseModel, ConfigDict, field_validator
from scipy.spatial.transform import Rotation


class CameraExtrinsics(BaseModel, TomlMixin):
    """Camera extrinsic parameters: orientation (quaternion wxyz) + translation."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    quaternion_wxyz: NDArray[np.float64]
    translation: NDArray[np.float64]

    @field_validator("quaternion_wxyz", mode="before")
    @classmethod
    def validate_quaternion(cls, v: NDArray[np.float64] | list) -> NDArray[np.float64]:
        arr = np.asarray(v, dtype=np.float64).ravel()
        if arr.shape != (4,):
            raise ValueError(f"Quaternion must have shape (4,), got {arr.shape}")
        return arr

    @field_validator("translation", mode="before")
    @classmethod
    def validate_translation(cls, v: NDArray[np.float64] | list) -> NDArray[np.float64]:
        arr = np.asarray(v, dtype=np.float64).ravel()
        if arr.shape != (3,):
            raise ValueError(f"Translation must have shape (3,), got {arr.shape}")
        return arr

    @property
    def rotation_matrix(self) -> NDArray[np.float64]:
        """3x3 rotation matrix from quaternion."""
        w, x, y, z = self.quaternion_wxyz
        return Rotation.from_quat([x, y, z, w]).as_matrix()

    @property
    def rodrigues_vector(self) -> NDArray[np.float64]:
        """3-element Rodrigues rotation vector (for OpenCV compatibility)."""
        rvec, _ = cv2.Rodrigues(self.rotation_matrix)
        return rvec.ravel()

    @property
    def world_position(self) -> NDArray[np.float64]:
        """Camera position in world coordinates: -R^T @ t."""
        return -self.rotation_matrix.T @ self.translation

    @property
    def world_orientation(self) -> NDArray[np.float64]:
        """Camera orientation as 3x3 rotation matrix (cam-to-world): R^T."""
        return self.rotation_matrix.T

    @classmethod
    def from_rodrigues(
            cls,
            *,
            rvec: NDArray[np.float64],
            tvec: NDArray[np.float64],
    ) -> "CameraExtrinsics":
        """Construct from Rodrigues rotation vector + translation."""
        rmat, _ = cv2.Rodrigues(np.asarray(rvec, dtype=np.float64).ravel())
        quat_xyzw = Rotation.from_matrix(rmat).as_quat()
        quat_wxyz = np.array(
            [quat_xyzw[3], quat_xyzw[0], quat_xyzw[1], quat_xyzw[2]],
        )
        return cls(
            quaternion_wxyz=quat_wxyz,
            translation=np.asarray(tvec, dtype=np.float64).ravel(),
        )

    @classmethod
    def identity(cls) -> "CameraExtrinsics":
        """Identity transform (no rotation, no translation)."""
        return cls(
            quaternion_wxyz=np.array([1.0, 0.0, 0.0, 0.0]),
            translation=np.zeros(3, dtype=np.float64),
        )
