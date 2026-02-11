"""Pydantic data models for camera calibration via bundle adjustment."""

import cv2
import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from scipy.spatial.transform import Rotation


# =============================================================================
# BOARD DEFINITION
# =============================================================================


class CharucoBoardDefinition(BaseModel):
    """Known charuco board geometry — fixed, never optimized."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    squares_x: int
    squares_y: int
    square_length_mm: float
    marker_length_mm: float
    marker_bits: int = 4
    dict_size: int = 250

    @property
    def n_corners(self) -> int:
        """Number of internal corners on the board."""
        return (self.squares_x - 1) * (self.squares_y - 1)

    @property
    def corner_positions_board_frame(self) -> NDArray[np.float64]:
        """(n_corners, 3) corner positions in the board-local frame (Z=0 plane)."""
        cols = self.squares_x - 1
        rows = self.squares_y - 1
        objp = np.zeros((cols * rows, 3), dtype=np.float64)
        objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)
        objp *= self.square_length_mm
        return objp


# =============================================================================
# INTRINSICS
# =============================================================================


class IntrinsicsOptimizationMode(BaseModel):
    """Control which intrinsic parameters are free during optimization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    optimize_focal_length: bool = True
    shared_focal_length: bool = False
    optimize_principal_point: bool = False
    optimize_k1: bool = True
    optimize_k2: bool = False
    optimize_tangential: bool = False

    @property
    def constant_indices(self) -> list[int]:
        """Indices into the 8-element intrinsics array that should be held constant.

        Array layout: [fx, fy, cx, cy, k1, k2, p1, p2]
        """
        indices: list[int] = []
        if not self.optimize_focal_length:
            indices.extend([0, 1])
        if not self.optimize_principal_point:
            indices.extend([2, 3])
        if not self.optimize_k1:
            indices.append(4)
        if not self.optimize_k2:
            indices.append(5)
        if not self.optimize_tangential:
            indices.extend([6, 7])
        return sorted(indices)


class CameraIntrinsics(BaseModel):
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
        """OpenCV distortion coefficients: [k1, k2, p1, p2]."""
        return np.array([self.k1, self.k2, self.p1, self.p2], dtype=np.float64)

    @classmethod
    def from_image_size(cls, *, width: int, height: int) -> "CameraIntrinsics":
        """Naive initial guess: focal length = image width, principal point = center."""
        return cls(
            fx=float(width),
            fy=float(width),
            cx=float(width) / 2.0,
            cy=float(height) / 2.0,
        )


# =============================================================================
# EXTRINSICS
# =============================================================================


class CameraExtrinsics(BaseModel):
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

    @classmethod
    def from_rodrigues(cls, *, rvec: NDArray[np.float64], tvec: NDArray[np.float64]) -> "CameraExtrinsics":
        """Construct from Rodrigues rotation vector + translation."""
        rmat, _ = cv2.Rodrigues(np.asarray(rvec, dtype=np.float64).ravel())
        quat_xyzw = Rotation.from_matrix(rmat).as_quat()
        quat_wxyz = np.array([quat_xyzw[3], quat_xyzw[0], quat_xyzw[1], quat_xyzw[2]])
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

    @property
    def world_position(self) -> NDArray[np.float64]:
        """Camera position in world coordinates: -R^T @ t."""
        return -self.rotation_matrix.T @ self.translation

    @property
    def world_orientation(self) -> NDArray[np.float64]:
        """Camera orientation as 3x3 rotation matrix (cam-to-world): R^T."""
        return self.rotation_matrix.T


# =============================================================================
# CAMERA MODEL
# =============================================================================


class CameraModel(BaseModel):
    """Complete camera model: intrinsics + extrinsics + metadata."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    name: str
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


# =============================================================================
# OBSERVATIONS
# =============================================================================


class CornerObservation(BaseModel):
    """A single detected charuco corner in pixel coordinates."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    corner_id: int
    pixel_xy: NDArray[np.float64]

    @field_validator("pixel_xy", mode="before")
    @classmethod
    def validate_pixel(cls, v: NDArray[np.float64] | list | tuple) -> NDArray[np.float64]:
        arr = np.asarray(v, dtype=np.float64).ravel()
        if arr.shape != (2,):
            raise ValueError(f"pixel_xy must have shape (2,), got {arr.shape}")
        return arr


class CharucoCornersObservation(BaseModel):
    """All charuco corners detected by one camera in one frame."""

    model_config = ConfigDict(extra="forbid")

    camera_name: str
    frame_index: int
    corners: list[CornerObservation]

    @property
    def n_corners(self) -> int:
        return len(self.corners)

    @property
    def corner_ids(self) -> list[int]:
        return [c.corner_id for c in self.corners]


# =============================================================================
# SOLVER CONFIG
# =============================================================================


class PyceresCalibrationSolverConfig(BaseModel):
    """Configuration for the bundle adjustment solver."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_iterations: int = 500
    function_tolerance: float = 1e-8
    parameter_tolerance: float = 1e-10
    gradient_tolerance: float = 1e-12
    intrinsics_mode: IntrinsicsOptimizationMode = IntrinsicsOptimizationMode()
    intrinsics_prior_weight: float = 0.01
    pin_camera_0: bool = True
    outlier_rejection_iterations: int = 5
    initial_outlier_threshold_px: float = 15.0
    final_outlier_threshold_px: float = 2.0
    min_corners_per_frame: int = 4

    @model_validator(mode="after")
    def validate_thresholds(self) -> "PyceresCalibrationSolverConfig":
        if self.initial_outlier_threshold_px < self.final_outlier_threshold_px:
            raise ValueError(
                f"initial_outlier_threshold_px ({self.initial_outlier_threshold_px}) "
                f"must be >= final_outlier_threshold_px ({self.final_outlier_threshold_px})"
            )
        return self


# =============================================================================
# RESULT
# =============================================================================


class CalibrationResult(BaseModel):
    """Output of the calibration pipeline."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    cameras: list[CameraModel]
    board: CharucoBoardDefinition
    reprojection_error_px: float
    initial_cost: float
    final_cost: float
    n_iterations: int
    time_seconds: float
    n_observations_used: int
    n_observations_rejected: int

    @property
    def camera_names(self) -> list[str]:
        return [c.name for c in self.cameras]

    def get_camera(self, name: str) -> CameraModel:
        """Look up a camera by name."""
        for cam in self.cameras:
            if cam.name == name:
                return cam
        raise KeyError(f"Camera '{name}' not found. Available: {self.camera_names}")
