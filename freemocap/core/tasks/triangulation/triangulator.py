"""Triangulator: pure DLT triangulation from CameraModel list.

Single source of triangulation in the codebase. One class, one public method
`triangulate(...)` that handles dict, 3D-array, and 4D-array inputs internally
and dispatches to either simple DLT or the subset-ensemble outlier-rejection
algorithm based on the supplied `TriangulationConfig`.

Pure numpy + cv2 (for undistortion). No aniposelib coupling.
"""
import logging
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, model_validator
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.tasks.calibration.shared.camera_model import CameraModel
from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from freemocap.core.tasks.triangulation.helpers.outlier_rejection import (
    triangulate_with_outlier_rejection,
)
from freemocap.core.tasks.triangulation.helpers.triangulate_simple import triangulate_simple
from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig
from freemocap.core.tasks.triangulation.helpers.triangulation_result import TriangulationResult

logger = logging.getLogger(__name__)

PointsByCamera = dict[str, NDArray[np.float64]]
PointsArray = NDArray[np.float64]
TriangulateInput = PointsByCamera | PointsArray


def _undistort_points_for_camera(
        *,
        points_2d: NDArray[np.float64],
        camera: CameraModel,
) -> NDArray[np.float64]:
    """Undistort 2D pixel points using camera intrinsics. Returns normalized coords."""
    pts = points_2d.reshape(-1, 1, 2).astype(np.float64)
    K = camera.intrinsics.to_camera_matrix()
    dist = camera.intrinsics.to_dist_coeffs()
    undistorted = cv2.undistortPoints(pts, K, dist)
    return undistorted.reshape(-1, 2)


class Triangulator(BaseModel):
    """Triangulates 2D observations into 3D using calibrated CameraModels."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    cameras: list[CameraModel]

    _extrinsics_mats: NDArray[np.float64] | None = None

    @model_validator(mode="after")
    def _precompute(self) -> "Triangulator":
        if len(self.cameras) < 2:
            raise ValueError(f"Triangulator requires at least 2 cameras, got {len(self.cameras)}")
        ext = np.zeros((len(self.cameras), 3, 4), dtype=np.float64)
        for i, cam in enumerate(self.cameras):
            ext[i, :, :3] = cam.extrinsics.rotation_matrix
            ext[i, :, 3] = cam.extrinsics.translation
        object.__setattr__(self, "_extrinsics_mats", ext)
        return self

    @property
    def camera_ids(self) -> list[str]:
        return [cam.id for cam in self.cameras]

    @property
    def n_cameras(self) -> int:
        return len(self.cameras)

    # =========================================================================
    # CONSTRUCTION HELPERS
    # =========================================================================

    @classmethod
    def from_calibration_result(cls, calibration: CalibrationResult) -> "Triangulator":
        return cls(cameras=calibration.cameras)

    @classmethod
    def from_calibration_for_cameras(
            cls,
            calibration: CalibrationResult,
            camera_ids: list[CameraIdString],
    ) -> "Triangulator":
        """Build a triangulator with cameras ordered to match camera_ids."""
        calibration_cameras_by_id = {cam.id: cam for cam in calibration.cameras}
        ordered_cameras: list[CameraModel] = []
        for cam_id in camera_ids:
            # TODO - Should add more robust camera matching method here. Camera ID's are not stable across (say) reboot, but there might be a way to match by index, or even by min reproj err
            if cam_id not in calibration_cameras_by_id:
                raise KeyError(
                    f"Camera '{cam_id}' not found in calibration. "
                    f"Calibration contains: {list(calibration_cameras_by_id.keys())}"
                )
            ordered_cameras.append(calibration_cameras_by_id[cam_id])
        return cls(cameras=ordered_cameras)

    @classmethod
    def from_anipose_calibration_toml(cls, path: str | Path) -> "Triangulator":
        result = CalibrationResult.load_anipose_toml(Path(path))
        return cls.from_calibration_result(calibration=result)

    def subset(self, camera_ids: list[CameraIdString]) -> "Triangulator":
        """Return a new Triangulator restricted to the named cameras (preserving order of camera_names)."""
        by_id = {cam.id: cam for cam in self.cameras}
        missing = [n for n in camera_ids if n not in by_id]
        if missing:
            raise KeyError(f"Unknown cameras: {missing}. Known: {self.camera_ids}")
        return Triangulator(cameras=[by_id[n] for n in camera_ids])

    # =========================================================================
    # PROJECTION
    # =========================================================================

    def project(self, points_3d: NDArray[np.float64]) -> NDArray[np.float64]:
        """Project 3D points through all cameras (with intrinsics + distortion).

        Args:
            points_3d: shape (n_points, 3) world coordinates. NaN-rows are skipped.

        Returns:
            shape (n_cameras, n_points, 2) pixel coordinates. NaN where the
            corresponding 3D point was NaN.
        """
        n_points = points_3d.shape[0]
        out = np.empty((self.n_cameras, n_points, 2), dtype=np.float64)
        nan_mask = np.isnan(points_3d).any(axis=1)
        valid_pts = points_3d[~nan_mask].reshape(-1, 1, 3)
        for cam_idx, cam in enumerate(self.cameras):
            if valid_pts.shape[0] == 0:
                out[cam_idx] = np.nan
                continue
            rvec = cam.extrinsics.rodrigues_vector
            tvec = cam.extrinsics.translation
            K = cam.intrinsics.to_camera_matrix()
            dist = cam.intrinsics.to_dist_coeffs()
            projected, _ = cv2.projectPoints(valid_pts, rvec, tvec, K, dist)
            full = np.full((n_points, 2), np.nan, dtype=np.float64)
            full[~nan_mask] = projected.reshape(-1, 2)
            out[cam_idx] = full
        return out

    # =========================================================================
    # CORE TRIANGULATION
    # =========================================================================

    def triangulate(
            self,
            *,
            data2d: TriangulateInput,
            config: TriangulationConfig | None = None,
            assume_undistorted_normalized: bool = False,
            camera_order: list[CameraIdString] | None = None,
    ) -> TriangulationResult:
        """Triangulate 2D pixel observations into 3D.

        Accepts either:
            - dict[camera_name, NDArray of shape (n_frames, n_points, 2)]
            - NDArray of shape (n_cameras, n_points, 2)             [single-frame batch]
            - NDArray of shape (n_cameras, n_frames, n_points, 2)   [multi-frame batch]

        Camera ordering is matched by name for dicts. For array input, the
        first axis is positionally aligned with `self.cameras` — the caller
        is responsible for that alignment. Pass `camera_order` (a list of
        camera names matching the array's first axis) to assert that
        alignment explicitly; if it doesn't match `self.camera_names`,
        triangulation raises rather than silently producing garbage 3D.

        If `assume_undistorted_normalized=True`, callers must pass already-undistorted
        normalized coordinates (intrinsics-removed); used by the calibration solver
        path that handles undistortion itself. The reprojection error in the result
        is then also reported in normalized coords.

        Returns a `TriangulationResult` whose array shapes mirror the input rank:
            - single-frame array input -> points_3d (n_points, 3)
            - dict / 4D array input    -> points_3d (n_frames, n_points, 3)
        """
        if config is None:
            config = TriangulationConfig()

        if camera_order is not None and camera_order != self.camera_ids:
            # TODO - This dumb, we should do better than this
            raise ValueError(
                f"camera_order does not match this Triangulator's camera order. "
                f"Got {camera_order}, expected {self.camera_ids}. Either reorder "
                f"the input array's first axis to match, or rebuild the Triangulator "
                f"via Triangulator.from_calibration_for_cameras(...) with the desired order."
            )

        stacked, was_single_frame, n_frames, n_points = self._normalize_input(data2d=data2d)

        if assume_undistorted_normalized:
            undistorted = stacked
        else:
            undistorted = np.empty_like(stacked)
            for cam_idx, cam in enumerate(self.cameras):
                flat_in = stacked[cam_idx].reshape(-1, 2)
                flat_out = _undistort_points_for_camera(points_2d=flat_in, camera=cam)
                undistorted[cam_idx] = flat_out.reshape(n_frames, n_points, 2)

        # Flatten frames * points -> (n_cameras, n_flat, 2)
        n_flat = n_frames * n_points
        und_flat = undistorted.reshape(self.n_cameras, n_flat, 2)

        points_3d_flat = np.full((n_flat, 3), np.nan, dtype=np.float64)
        weights_flat = np.full((n_flat, self.n_cameras), np.nan, dtype=np.float64)

        for pt_idx in range(n_flat):
            subp = und_flat[:, pt_idx, :]  # (n_cameras, 2)
            valid = ~np.isnan(subp[:, 0])
            n_valid = int(np.sum(valid))
            if n_valid < config.minimum_cameras_for_triangulation:
                continue

            valid_idx = np.where(valid)[0]
            valid_pts = subp[valid_idx]
            valid_ext = self._extrinsics_mats[valid_idx]

            if config.use_outlier_rejection:
                p3d, cam_weights_valid = triangulate_with_outlier_rejection(
                    points_2d=valid_pts,
                    extrinsics_mats=valid_ext,
                    minimum_cameras_for_triangulation=config.minimum_cameras_for_triangulation,
                    maximum_cameras_to_drop=config.maximum_cameras_to_drop,
                    target_reprojection_error=config.target_reprojection_error,
                )
            else:
                p3d = triangulate_simple(points=valid_pts, extrinsics_mats=valid_ext)
                cam_weights_valid = np.full(n_valid, 1.0 / n_valid, dtype=np.float64)

            points_3d_flat[pt_idx] = p3d
            weights_flat[pt_idx, valid_idx] = cam_weights_valid

        if assume_undistorted_normalized:
            reprojection_error_flat = self._compute_reprojection_error_flat_normalized(
                points_3d_flat=points_3d_flat,
                data2d_normalized_flat=stacked.reshape(self.n_cameras, n_flat, 2),
            )
        else:
            reprojection_error_flat = self._compute_reprojection_error_flat(
                points_3d_flat=points_3d_flat,
                data2d_pixel_flat=stacked.reshape(self.n_cameras, n_flat, 2),
            )

        # Reshape outputs
        if was_single_frame:
            points_3d = points_3d_flat.reshape(n_points, 3)
            per_camera_weights = weights_flat.reshape(n_points, self.n_cameras)
            reprojection_error = reprojection_error_flat.reshape(self.n_cameras, n_points)
        else:
            points_3d = points_3d_flat.reshape(n_frames, n_points, 3)
            per_camera_weights = weights_flat.reshape(n_frames, n_points, self.n_cameras)
            reprojection_error = reprojection_error_flat.reshape(self.n_cameras, n_frames, n_points)

        return TriangulationResult(
            points_3d=points_3d,
            per_camera_weights=per_camera_weights,
            reprojection_error=reprojection_error,
        )

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    def _normalize_input(
            self,
            *,
            data2d: TriangulateInput,
    ) -> tuple[NDArray[np.float64], bool, int, int]:
        """Normalize all accepted input shapes to (n_cameras, n_frames, n_points, 2).

        Returns (stacked, was_single_frame, n_frames, n_points).
        """
        if isinstance(data2d, dict):
            return self._normalize_dict(points_2d_by_camera=data2d)

        arr = np.asarray(data2d, dtype=np.float64)
        if arr.ndim == 3:
            n_cams, n_points, n_dims = arr.shape
            if n_cams != self.n_cameras:
                raise ValueError(
                    f"data2d has {n_cams} cameras but triangulator has {self.n_cameras}"
                )
            if n_dims not in (2, 3):
                raise ValueError(f"Last dim must be 2 (xy) or 3 (xyz, slicing :2), got {n_dims}")
            stacked = arr[..., :2].reshape(n_cams, 1, n_points, 2)
            return stacked, True, 1, n_points

        if arr.ndim == 4:
            n_cams, n_frames, n_points, n_dims = arr.shape
            if n_cams != self.n_cameras:
                raise ValueError(
                    f"data2d has {n_cams} cameras but triangulator has {self.n_cameras}"
                )
            if n_dims not in (2, 3):
                raise ValueError(f"Last dim must be 2 (xy) or 3 (xyz, slicing :2), got {n_dims}")
            return arr[..., :2], False, n_frames, n_points

        raise ValueError(
            f"data2d array must be 3D (n_cameras, n_points, 2) or 4D "
            f"(n_cameras, n_frames, n_points, 2); got ndim={arr.ndim}, shape={arr.shape}"
        )

    def _normalize_dict(
            self,
            *,
            points_2d_by_camera: PointsByCamera,
    ) -> tuple[NDArray[np.float64], bool, int, int]:
        id_to_idx = {name: i for i, name in enumerate(self.camera_ids)}
        for camera_id in points_2d_by_camera:
            if camera_id not in id_to_idx:
                raise KeyError(
                    f"Camera '{camera_id}' not found in triangulator. "
                    f"Known cameras: {self.camera_ids}"
                )

        first_array = next(iter(points_2d_by_camera.values()))
        if first_array.ndim != 3 or first_array.shape[2] != 2:
            raise ValueError(
                f"Expected dict values of shape (n_frames, n_points, 2), got {first_array.shape}"
            )
        n_frames, n_points = first_array.shape[0], first_array.shape[1]

        stacked = np.full(
            (self.n_cameras, n_frames, n_points, 2), np.nan, dtype=np.float64,
        )
        for camera_id, data in points_2d_by_camera.items():
            if data.shape != (n_frames, n_points, 2):
                raise ValueError(
                    f"Camera '{camera_id}' has shape {data.shape}, "
                    f"expected ({n_frames}, {n_points}, 2)"
                )
            stacked[id_to_idx[camera_id]] = data.astype(np.float64, copy=False)

        return stacked, False, n_frames, n_points

    def _compute_reprojection_error_flat(
            self,
            *,
            points_3d_flat: NDArray[np.float64],
            data2d_pixel_flat: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Compute per-camera Euclidean pixel reprojection error. Returns (n_cameras, n_flat)."""
        projected = self.project(points_3d=points_3d_flat)
        diff = data2d_pixel_flat - projected
        nan_mask = np.isnan(data2d_pixel_flat).any(axis=2)
        norm = np.linalg.norm(diff, axis=2)
        norm[nan_mask] = np.nan
        return norm

    def _compute_reprojection_error_flat_normalized(
            self,
            *,
            points_3d_flat: NDArray[np.float64],
            data2d_normalized_flat: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Per-camera Euclidean reprojection error in undistorted-normalized coords."""
        n_flat = points_3d_flat.shape[0]
        out = np.full((self.n_cameras, n_flat), np.nan, dtype=np.float64)
        for cam_idx in range(self.n_cameras):
            ext = self._extrinsics_mats[cam_idx]
            for pt_idx in range(n_flat):
                obs = data2d_normalized_flat[cam_idx, pt_idx]
                if np.isnan(obs).any() or np.isnan(points_3d_flat[pt_idx]).any():
                    continue
                hom = np.array(
                    [points_3d_flat[pt_idx, 0], points_3d_flat[pt_idx, 1],
                     points_3d_flat[pt_idx, 2], 1.0],
                    dtype=np.float64,
                )
                proj = ext @ hom
                proj_2d = proj[:2] / proj[2]
                out[cam_idx, pt_idx] = float(np.linalg.norm(proj_2d - obs))
        return out

    # =========================================================================
    # REPROJECTION ERROR (public helpers used by callers that already have 3D)
    # =========================================================================

    def signed_reprojection_error(
            self,
            *,
            points_3d: NDArray[np.float64],
            points_2d_pixel: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Signed pixel reprojection error per camera, per point.

        Args:
            points_3d: (n_points, 3) world coordinates.
            points_2d_pixel: (n_cameras, n_points, 2) pixel observations.

        Returns:
            (n_cameras, n_points, 2) signed error = observation - projection.
            NaN where the original observation was NaN.
        """
        projected = self.project(points_3d=points_3d)
        error = points_2d_pixel - projected
        nan_mask = np.isnan(points_2d_pixel)
        error[nan_mask] = np.nan
        return error

    def mean_reprojection_error(
            self,
            *,
            points_3d: NDArray[np.float64],
            points_2d_pixel: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Mean Euclidean reprojection error per point, averaged across valid cameras.

        Returns shape (n_points,) - NaN for points with fewer than 2 valid observations.
        """
        signed = self.signed_reprojection_error(
            points_3d=points_3d, points_2d_pixel=points_2d_pixel,
        )
        norm = np.linalg.norm(signed, axis=2)  # (n_cameras, n_points)
        valid = ~np.isnan(norm)
        norm_zeroed = np.where(valid, norm, 0.0)
        denom = np.sum(valid, axis=0).astype(np.float64)
        denom[denom < 1.5] = np.nan
        return np.sum(norm_zeroed, axis=0) / denom
