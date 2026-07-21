import numpy as np
from freemocap.utilities.toml_mixin import TomlMixin
from numpy._typing import NDArray
from pydantic import BaseModel, ConfigDict


class CameraIntrinsics(BaseModel, TomlMixin):
    """Camera intrinsic parameters: focal length, principal point, distortion."""

    model_config = ConfigDict(extra="forbid")

    fx: float
    fy: float
    cx: float
    cy: float
    k1: float = 0.0
    k2: float = 0.0
    p1: float = 0.0
    p2: float = 0.0

    def to_param_array(self) -> NDArray[np.float64]:
        """Pack into 8-element array: [fx, fy, cx, cy, k1, k2, p1, p2]."""
        return np.array(
            [self.fx, self.fy, self.cx, self.cy, self.k1, self.k2, self.p1, self.p2],
            dtype=np.float64,
        )

    @classmethod
    def from_param_array(cls, params: NDArray[np.float64]) -> "CameraIntrinsics":
        """Unpack from 8-element array."""
        if params.shape != (8,):
            raise ValueError(f"Expected shape (8,), got {params.shape}")
        return cls(
            fx=float(params[0]),
            fy=float(params[1]),
            cx=float(params[2]),
            cy=float(params[3]),
            k1=float(params[4]),
            k2=float(params[5]),
            p1=float(params[6]),
            p2=float(params[7]),
        )

    def to_camera_matrix(self) -> NDArray[np.float64]:
        """3x3 camera matrix K."""
        return np.array(
            [[self.fx, 0.0, self.cx],
             [0.0, self.fy, self.cy],
             [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )

    def to_dist_coeffs(self) -> NDArray[np.float64]:
        """OpenCV distortion coefficients (4-element): [k1, k2, p1, p2]."""
        return np.array([self.k1, self.k2, self.p1, self.p2], dtype=np.float64)

    def to_dist_coeffs_5(self) -> NDArray[np.float64]:
        """5-element distortion vector for anipose-compatible TOML: [k1, k2, p1, p2, 0]."""
        return np.array([self.k1, self.k2, self.p1, self.p2, 0.0], dtype=np.float64)

    @classmethod
    def from_image_size(cls, *, width: int, height: int) -> "CameraIntrinsics":
        """Naive initial guess: focal length = image width, principal point = center."""
        return cls(
            fx=float(width),
            fy=float(width),
            cx=float(width) / 2.0,
            cy=float(height) / 2.0,
        )

    @classmethod
    def from_camera_matrix_and_dist(
            cls,
            *,
            camera_matrix: NDArray[np.float64],
            dist_coeffs: NDArray[np.float64],
    ) -> "CameraIntrinsics":
        """Construct from a 3x3 camera matrix and distortion coefficients."""
        if camera_matrix.shape != (3, 3):
            raise ValueError(f"camera_matrix shape {camera_matrix.shape}, expected (3, 3)")
        dist = dist_coeffs.ravel()
        return cls(
            fx=float(camera_matrix[0, 0]),
            fy=float(camera_matrix[1, 1]),
            cx=float(camera_matrix[0, 2]),
            cy=float(camera_matrix[1, 2]),
            k1=float(dist[0]) if len(dist) > 0 else 0.0,
            k2=float(dist[1]) if len(dist) > 1 else 0.0,
            p1=float(dist[2]) if len(dist) > 2 else 0.0,
            p2=float(dist[3]) if len(dist) > 3 else 0.0,
        )
