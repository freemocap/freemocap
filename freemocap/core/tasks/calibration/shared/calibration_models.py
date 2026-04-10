"""Shared Pydantic data models for camera calibration.

These models are the canonical representations used by both the anipose
and pyceres calibration paths. Each solver may have additional internal
models, but data flows through these shared types at the boundaries.
"""

from pathlib import Path

import cv2
import numpy as np
import toml
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, field_validator, model_validator, computed_field
from scipy.spatial.transform import Rotation

from freemocap.utilities.toml_mixin import TomlMixin, numpy_to_python


# =============================================================================
# BOARD DEFINITION
# =============================================================================


class CharucoBoardDefinition(BaseModel, TomlMixin):
    """Known charuco board geometry — fixed, never optimized.

    Single source of truth for board parameters. Both solver paths
    construct their solver-specific board representations from this.
    """

    model_config = ConfigDict(extra="forbid")

    squares_x: int
    squares_y: int
    square_length_mm: float
    marker_length_ratio: float = 0.8
    marker_bits: int = 4
    dict_size: int = 250

    @computed_field
    @property
    def aruco_marker_length_mm(self) -> float:
        return self.marker_length_ratio * self.square_length_mm

    @model_validator(mode="after")
    def validate_geometry(self) -> "CharucoBoardDefinition":
        if self.aruco_marker_length_mm >= self.square_length_mm:
            raise ValueError(
                f"marker_length_mm ({self.aruco_marker_length_mm}) must be < "
                f"square_length_mm ({self.square_length_mm})"
            )
        if self.squares_x < 2 or self.squares_y < 2:
            raise ValueError(
                f"Board must have at least 2x2 squares, "
                f"got {self.squares_x}x{self.squares_y}"
            )
        return self

    @property
    def n_corners(self) -> int:
        """
        Number of internal corners on the board, i.e. corners between
        adjacent aruco markers. These are the points used as input to the calibrator
        """
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

    @classmethod
    def create_test_data_7x5(cls) -> "CharucoBoardDefinition":
        """Convenience method to create a standard 7x5 charuco board definition."""
        return cls(
            squares_x=7,
            squares_y=5,
            square_length_mm=58.0,
        )

    @classmethod
    def create_letter_size_5x3(cls) -> "CharucoBoardDefinition":
        """Convenience method to create a standard 7x5 charuco board definition."""
        return cls(
            squares_x=5,
            squares_y=3,
            square_length_mm=54.0,
        )

# =============================================================================
# INTRINSICS
# =============================================================================


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


# =============================================================================
# EXTRINSICS
# =============================================================================


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


# =============================================================================
# CAMERA MODEL
# =============================================================================


class CameraModel(BaseModel, TomlMixin):
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
# CALIBRATION RESULT
# =============================================================================



class CalibrationResult(BaseModel, TomlMixin):
    """Output of either calibration pipeline.

    Both the anipose and pyceres paths produce this type. It can be
    serialized to/from the anipose-compatible TOML format.

    Provides get_triangulator() and get_triangulator_for_cameras() to
    build a Triangulator for downstream 3D reconstruction without any
    anipose dependency.
    """

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

    # ---- Triangulator construction ----

    def get_triangulator(self) -> "Triangulator":
        """Build a Triangulator from this calibration's cameras.

        The Triangulator performs DLT triangulation directly from CameraModel
        intrinsics/extrinsics with no anipose dependency.
        """
        from freemocap.core.tasks.calibration.shared.triangulator import Triangulator
        return Triangulator.from_calibration_result(calibration=self)

    def get_triangulator_for_cameras(self, camera_ids: list[str]) -> "Triangulator":
        """Build a Triangulator with cameras ordered to match the given IDs.

        Use this when the current session's cameras may be a subset of,
        or in a different order than, the calibration's cameras.

        Raises:
            KeyError: If any camera_id is not found in this calibration.
        """
        from freemocap.core.tasks.calibration.shared.triangulator import Triangulator

        return Triangulator.from_calibration_for_cameras(
            calibration=self,
            camera_ids=camera_ids,
        )

    # ---- Anipose-compatible TOML (same as existing) ----

    def dump_anipose_toml(
        self,
        path: Path,
        metadata: dict | None = None,
    ) -> None:
        """Write anipose-compatible TOML."""
        cameras_dict: dict[str, object] = {}

        for cam in self.cameras:
            cameras_dict[cam.name] = {
                "name": cam.name,
                "size": list(cam.image_size),
                "matrix": cam.intrinsics.to_camera_matrix().tolist(),
                "distortions": cam.intrinsics.to_dist_coeffs_5().tolist(),
                "rotation": cam.extrinsics.rodrigues_vector.tolist(),
                "translation": cam.extrinsics.translation.tolist(),
                "world_orientation": cam.extrinsics.world_orientation.tolist(),
                "world_position": cam.extrinsics.world_position.tolist(),
            }

        meta = metadata.copy() if metadata else {}
        meta["reprojection_error_px"] = self.reprojection_error_px
        meta["n_observations_used"] = self.n_observations_used
        meta["n_observations_rejected"] = self.n_observations_rejected
        meta["solver_time_seconds"] = self.time_seconds
        meta["board"] = {
            "squares_x": self.board.squares_x,
            "squares_y": self.board.squares_y,
            "square_length_mm": self.board.square_length_mm,
            "marker_length_mm": self.board.aruco_marker_length_mm,
            "marker_bits": self.board.marker_bits,
            "dict_size": self.board.dict_size,
        }
        cameras_dict["metadata"] = numpy_to_python(meta)

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(toml.dumps(cameras_dict))

    @classmethod
    def load_anipose_toml(cls, path: Path) -> "CalibrationResultUpdated":
        """Load from an anipose-compatible TOML calibration file."""
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"Calibration file not found: {path}")

        toml_data = toml.load(path)
        metadata = toml_data.pop("metadata", {})

        cameras: list[CameraModel] = []
        for key in sorted(toml_data.keys()):
            d = toml_data[key]
            if "name" not in d:
                raise ValueError(f"TOML key '{key}' missing 'name' field")

            if "size" in d:
                size = (int(d["size"][0]), int(d["size"][1]))
            elif "image_size" in d:
                size = (int(d["image_size"][0]), int(d["image_size"][1]))
            else:
                raise KeyError(f"Camera '{key}' missing 'size' or 'image_size'")

            K = np.array(d["matrix"], dtype=np.float64)
            if K.shape != (3, 3):
                raise ValueError(f"Camera '{key}': matrix shape {K.shape}, expected (3, 3)")

            dist = np.array(d["distortions"], dtype=np.float64).ravel()

            intrinsics = CameraIntrinsics(
                fx=float(K[0, 0]),
                fy=float(K[1, 1]),
                cx=float(K[0, 2]),
                cy=float(K[1, 2]),
                k1=float(dist[0]) if len(dist) > 0 else 0.0,
                k2=float(dist[1]) if len(dist) > 1 else 0.0,
                p1=float(dist[2]) if len(dist) > 2 else 0.0,
                p2=float(dist[3]) if len(dist) > 3 else 0.0,
            )

            rvec = np.array(d["rotation"], dtype=np.float64).ravel()
            tvec = np.array(d["translation"], dtype=np.float64).ravel()
            extrinsics = CameraExtrinsics.from_rodrigues(rvec=rvec, tvec=tvec)

            cameras.append(
                CameraModel(
                    name=str(d["name"]),
                    image_size=size,
                    intrinsics=intrinsics,
                    extrinsics=extrinsics,
                )
            )

        if len(cameras) == 0:
            raise ValueError(f"No cameras found in {path}")

        board_meta = metadata.get("board", {})
        board = CharucoBoardDefinition(
            squares_x=board_meta.get("squares_x", 7),
            squares_y=board_meta.get("squares_y", 5),
            square_length_mm=board_meta.get("square_length_mm", 1.0),
            # aruco_marker_length_mm=board_meta.get("marker_length_mm", 0.8),
            marker_bits=board_meta.get("marker_bits", 4),
            dict_size=board_meta.get("dict_size", 250),
        )

        return cls(
            cameras=cameras,
            board=board,
            reprojection_error_px=metadata.get("reprojection_error_px", 0.0),
            initial_cost=metadata.get("initial_cost", 0.0),
            final_cost=metadata.get("final_cost", 0.0),
            n_iterations=metadata.get("n_iterations", 0),
            time_seconds=metadata.get("solver_time_seconds", 0.0),
            n_observations_used=metadata.get("n_observations_used", 0),
            n_observations_rejected=metadata.get("n_observations_rejected", 0),
        )
