"""Triangulator: pure DLT triangulation from CameraModel list.

No dependency on anipose. Works directly with the Pydantic CameraModel
and CalibrationResult types from calibration_models.py.
"""

import logging

import cv2
import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, model_validator

from freemocap.core.tasks.calibration.shared.calibration_models import CameraModel, CalibrationResult

logger = logging.getLogger(__name__)


def _undistort_points(
    points_2d: NDArray[np.float64],
    camera: CameraModel,
) -> NDArray[np.float64]:
    """Undistort 2D points using camera intrinsics. Returns normalized coordinates."""
    pts = points_2d.reshape(-1, 1, 2).astype(np.float64)
    K = camera.intrinsics.to_camera_matrix()
    dist = camera.intrinsics.to_dist_coeffs()
    undistorted = cv2.undistortPoints(pts, K, dist)
    return undistorted.reshape(-1, 2)


def _triangulate_single_point(
    normalized_points: NDArray[np.float64],
    extrinsics_mats: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Triangulate a single 3D point from undistorted+normalized 2D observations via DLT.

    Args:
        normalized_points: (N, 2) undistorted normalized coordinates for N cameras.
        extrinsics_mats: (N, 3, 4) [R|t] matrices for those N cameras.

    Returns:
        (3,) 3D point in world coordinates.
    """
    n_views = normalized_points.shape[0]
    A = np.zeros((n_views * 2, 4), dtype=np.float64)
    for i in range(n_views):
        x, y = normalized_points[i]
        P = extrinsics_mats[i]
        A[i * 2] = x * P[2] - P[0]
        A[i * 2 + 1] = y * P[2] - P[1]

    _, _, vh = np.linalg.svd(A, full_matrices=True)
    p_homogeneous = vh[-1]
    return p_homogeneous[:3] / p_homogeneous[3]


class Triangulator(BaseModel):
    """Triangulates 2D observations into 3D using calibrated CameraModels.

    Constructed from a list of CameraModel (as produced by CalibrationResult).
    Camera ordering is determined by the order of the cameras list.
    All input data must follow this same ordering.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    cameras: list[CameraModel]

    # Precomputed arrays cached after construction
    _extrinsics_mats: NDArray[np.float64] | None = None
    _projection_mats: NDArray[np.float64] | None = None

    @model_validator(mode="after")
    def _precompute(self) -> "Triangulator":
        if len(self.cameras) < 2:
            raise ValueError(f"Triangulator requires at least 2 cameras, got {len(self.cameras)}")
        # Precompute [R|t] and P matrices for each camera
        ext = np.zeros((len(self.cameras), 3, 4), dtype=np.float64)
        proj = np.zeros((len(self.cameras), 3, 4), dtype=np.float64)
        for i, cam in enumerate(self.cameras):
            R = cam.extrinsics.rotation_matrix
            t = cam.extrinsics.translation
            ext[i, :, :3] = R
            ext[i, :, 3] = t
            proj[i] = cam.projection_matrix
        object.__setattr__(self, "_extrinsics_mats", ext)
        object.__setattr__(self, "_projection_mats", proj)
        return self

    @property
    def camera_names(self) -> list[str]:
        return [cam.name for cam in self.cameras]

    @property
    def n_cameras(self) -> int:
        return len(self.cameras)

    # =========================================================================
    # CONSTRUCTION HELPERS
    # =========================================================================

    @classmethod
    def from_calibration_result(cls, calibration: CalibrationResult) -> "Triangulator":
        """Build a triangulator using all cameras from a CalibrationResult."""
        return cls(cameras=calibration.cameras)

    @classmethod
    def from_calibration_for_cameras(
        cls,
        calibration: CalibrationResult,
        camera_ids: list[str],
    ) -> "Triangulator":
        """Build a triangulator with cameras ordered to match camera_ids.

        Each camera_id must exactly match a CameraModel.name in the calibration.
        The resulting Triangulator's camera ordering matches the camera_ids ordering.

        Raises:
            KeyError: If any camera_id is not found in the calibration.
        """
        calibration_cameras_by_name = {cam.name: cam for cam in calibration.cameras}
        ordered_cameras: list[CameraModel] = []
        for cam_id in camera_ids:
            if cam_id not in calibration_cameras_by_name:
                raise KeyError(
                    f"Camera '{cam_id}' not found in calibration. "
                    f"Calibration contains: {list(calibration_cameras_by_name.keys())}"
                )
            ordered_cameras.append(calibration_cameras_by_name[cam_id])
        return cls(cameras=ordered_cameras)

    @classmethod
    def from_calibration_toml(cls, path: str) -> "Triangulator":
        """Load a calibration TOML and build a triangulator from all its cameras."""
        from pathlib import Path as _Path
        result = CalibrationResult.load_anipose_toml(_Path(path))
        return cls.from_calibration_result(calibration=result)

    # =========================================================================
    # CORE TRIANGULATION
    # =========================================================================

    def triangulate_points(
        self,
        points_2d: NDArray[np.float64],
        undistort: bool = True,
    ) -> NDArray[np.float64]:
        """Triangulate 2D points to 3D via DLT.

        Args:
            points_2d: (n_cameras, n_points, 2) array of 2D pixel coordinates.
                       NaN entries indicate a missing observation for that camera/point.
            undistort: If True, undistort points using camera intrinsics before
                       triangulating. Set to False if points are already normalized.

        Returns:
            (n_points, 3) array of 3D world coordinates. Points with fewer than
            2 valid observations are filled with NaN.
        """
        n_cams, n_points, _ = points_2d.shape
        if n_cams != self.n_cameras:
            raise ValueError(
                f"points_2d has {n_cams} cameras but triangulator has {self.n_cameras}"
            )

        # Undistort all points
        if undistort:
            undistorted = np.empty_like(points_2d)
            for cam_idx, cam in enumerate(self.cameras):
                undistorted[cam_idx] = _undistort_points(
                    points_2d=points_2d[cam_idx],
                    camera=cam,
                )
        else:
            undistorted = points_2d

        # Triangulate each point
        out = np.full((n_points, 3), np.nan, dtype=np.float64)
        for pt_idx in range(n_points):
            subp = undistorted[:, pt_idx, :]
            valid = ~np.isnan(subp[:, 0])
            if np.sum(valid) < 2:
                continue
            out[pt_idx] = _triangulate_single_point(
                normalized_points=subp[valid],
                extrinsics_mats=self._extrinsics_mats[valid],
            )

        return out

    def triangulate_dict(
        self,
        points_2d_by_camera: dict[str, NDArray[np.float64]],
    ) -> NDArray[np.float64]:
        """Triangulate from a dict of {camera_name: (n_frames, n_points, 2)}.

        Camera ordering is matched by name. Raises if a camera name is unknown.

        Returns:
            (n_frames, n_points, 3) array of triangulated 3D coordinates.
        """
        name_to_idx = {name: i for i, name in enumerate(self.camera_names)}

        # Validate camera names
        for cam_name in points_2d_by_camera:
            if cam_name not in name_to_idx:
                raise KeyError(
                    f"Camera '{cam_name}' not found in triangulator. "
                    f"Known cameras: {self.camera_names}"
                )

        # Determine shape from first entry
        first_array = next(iter(points_2d_by_camera.values()))
        if first_array.ndim != 3 or first_array.shape[2] != 2:
            raise ValueError(
                f"Expected arrays of shape (n_frames, n_points, 2), got {first_array.shape}"
            )
        n_frames = first_array.shape[0]
        n_points = first_array.shape[1]

        # Stack into (n_cameras, n_frames, n_points, 2) in triangulator camera order
        stacked = np.full(
            (self.n_cameras, n_frames, n_points, 2), np.nan, dtype=np.float64,
        )
        for cam_name, data in points_2d_by_camera.items():
            if data.shape != (n_frames, n_points, 2):
                raise ValueError(
                    f"Camera '{cam_name}' has shape {data.shape}, "
                    f"expected ({n_frames}, {n_points}, 2)"
                )
            stacked[name_to_idx[cam_name]] = data

        return self.triangulate_array(data2d=stacked)

    def triangulate_array(
        self,
        data2d: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Triangulate from a (n_cameras, n_frames, n_points, 2) array.

        Camera ordering must match self.cameras ordering.

        Returns:
            (n_frames, n_points, 3) array.
        """
        n_cameras, n_frames, n_points, n_dims = data2d.shape
        if n_cameras != self.n_cameras:
            raise ValueError(
                f"data2d has {n_cameras} cameras but triangulator has {self.n_cameras}"
            )
        if n_dims == 3:
            data2d = data2d[..., :2]

        # Flatten frames*points, triangulate, reshape
        flat = data2d.reshape(n_cameras, -1, 2)
        triangulated_flat = self.triangulate_points(points_2d=flat)
        return triangulated_flat.reshape(n_frames, n_points, 3)

    # =========================================================================
    # REPROJECTION
    # =========================================================================

    def project(self, points_3d: NDArray[np.float64]) -> NDArray[np.float64]:
        """Project 3D points through all cameras.

        Args:
            points_3d: (n_points, 3) world coordinates.

        Returns:
            (n_cameras, n_points, 2) pixel coordinates.
        """
        n_points = points_3d.shape[0]
        out = np.empty((self.n_cameras, n_points, 2), dtype=np.float64)
        pts = points_3d.reshape(-1, 1, 3)
        for cam_idx, cam in enumerate(self.cameras):
            rvec = cam.extrinsics.rodrigues_vector
            tvec = cam.extrinsics.translation
            K = cam.intrinsics.to_camera_matrix()
            dist = cam.intrinsics.to_dist_coeffs()
            projected, _ = cv2.projectPoints(pts, rvec, tvec, K, dist)
            out[cam_idx] = projected.reshape(n_points, 2)
        return out

    def reprojection_error(
        self,
        points_3d: NDArray[np.float64],
        points_2d: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Compute reprojection error.

        Args:
            points_3d: (n_points, 3) triangulated 3D points.
            points_2d: (n_cameras, n_points, 2) original 2D observations.

        Returns:
            (n_cameras, n_points, 2) signed reprojection error per camera per point.
            NaN where the original observation was NaN.
        """
        projected = self.project(points_3d=points_3d)
        error = points_2d - projected
        # Preserve NaN mask
        nan_mask = np.isnan(points_2d)
        error[nan_mask] = np.nan
        return error

    def mean_reprojection_error(
        self,
        points_3d: NDArray[np.float64],
        points_2d: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Mean reprojection error per point (across cameras).

        Returns:
            (n_points,) mean Euclidean reprojection error.
        """
        errors = self.reprojection_error(points_3d=points_3d, points_2d=points_2d)
        errors_norm = np.linalg.norm(errors, axis=2)  # (n_cameras, n_points)
        valid = ~np.isnan(errors_norm)
        errors_norm[~valid] = 0.0
        denom = np.sum(valid, axis=0).astype(np.float64)
        denom[denom < 1.5] = np.nan
        return np.sum(errors_norm, axis=0) / denom
