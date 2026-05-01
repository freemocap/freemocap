"""Triangulator: pure DLT triangulation from CameraModel list.

Single source of triangulation in the codebase. One class, one public method
`triangulate(...)` that handles dict, 3D-array, and 4D-array inputs internally
and dispatches to either simple DLT or the subset-ensemble outlier-rejection
algorithm based on the supplied `TriangulationConfig`.

Pure numpy + cv2 (for undistortion). No aniposelib coupling.
"""
import itertools
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
from freemocap.core.tasks.triangulation.helpers.triangulate_simple import triangulate_simple, triangulate_simple_batch
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
    # Cached per-camera cv2 inputs (computed once at construction, not on every project() call)
    _rvecs: list | None = None   # list of (3,1) Rodrigues vectors
    _tvecs: list | None = None   # list of (3,) translation vectors
    _Ks: list | None = None      # list of (3,3) camera matrices
    _dists: list | None = None   # list of distortion coefficient arrays

    @model_validator(mode="after")
    def _precompute(self) -> "Triangulator":
        if len(self.cameras) < 2:
            raise ValueError(f"Triangulator requires at least 2 cameras, got {len(self.cameras)}")
        ext = np.zeros((len(self.cameras), 3, 4), dtype=np.float64)
        rvecs, tvecs, Ks, dists = [], [], [], []
        for i, cam in enumerate(self.cameras):
            ext[i, :, :3] = cam.extrinsics.rotation_matrix
            ext[i, :, 3] = cam.extrinsics.translation
            rvecs.append(cam.extrinsics.rodrigues_vector.reshape(3, 1))
            tvecs.append(cam.extrinsics.translation)
            Ks.append(cam.intrinsics.to_camera_matrix())
            dists.append(cam.intrinsics.to_dist_coeffs())
        object.__setattr__(self, "_extrinsics_mats", ext)
        object.__setattr__(self, "_rvecs", rvecs)
        object.__setattr__(self, "_tvecs", tvecs)
        object.__setattr__(self, "_Ks", Ks)
        object.__setattr__(self, "_dists", dists)
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
        for cam_idx in range(self.n_cameras):
            if valid_pts.shape[0] == 0:
                out[cam_idx] = np.nan
                continue
            projected, _ = cv2.projectPoints(
                valid_pts, self._rvecs[cam_idx], self._tvecs[cam_idx],
                self._Ks[cam_idx], self._dists[cam_idx],
            )
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
            for cam_idx in range(self.n_cameras):
                pts = stacked[cam_idx].reshape(-1, 2).astype(np.float64)
                pts_cv = pts.reshape(-1, 1, 2)
                und = cv2.undistortPoints(pts_cv, self._Ks[cam_idx], self._dists[cam_idx])
                undistorted[cam_idx] = und.reshape(n_frames, n_points, 2)

        # Flatten frames * points -> (n_cameras, n_flat, 2)
        n_flat = n_frames * n_points
        und_flat = undistorted.reshape(self.n_cameras, n_flat, 2)

        points_3d_flat = np.full((n_flat, 3), np.nan, dtype=np.float64)
        weights_flat = np.full((n_flat, self.n_cameras), np.nan, dtype=np.float64)

        # Per-point validity: True where the 2D observation is not NaN.
        valid_all = ~np.isnan(und_flat[:, :, 0])  # (n_cameras, n_flat)
        n_valid_per_pt = valid_all.sum(axis=0)     # (n_flat,)

        # --- Batch path: points visible in ALL cameras (common case for RTMPose) ---
        all_cams_valid = valid_all.all(axis=0) & (n_valid_per_pt >= config.minimum_cameras_for_triangulation)
        batch_idx = np.where(all_cams_valid)[0]

        if batch_idx.size > 0:
            # (n_batch, n_cameras, 2) — rearrange from (n_cameras, n_batch, 2)
            pts_batch = np.ascontiguousarray(und_flat[:, batch_idx, :].transpose(1, 0, 2))
            p3d_batch = triangulate_simple_batch(
                points_batch=pts_batch, extrinsics_mats=self._extrinsics_mats
            )  # (n_batch, 3)

            if config.use_outlier_rejection:
                # Batch-project to check normalized reprojection error
                n_batch = batch_idx.size
                hom = np.concatenate(
                    [p3d_batch, np.ones((n_batch, 1), dtype=np.float64)], axis=1
                )  # (n_batch, 4)
                proj = self._extrinsics_mats @ hom.T  # (n_cameras, 3, n_batch)
                z = proj[:, 2, :]
                with np.errstate(invalid="ignore", divide="ignore"):
                    proj_2d = proj[:, :2, :] / z[:, None, :]  # (n_cameras, 2, n_batch)
                proj_2d_T = proj_2d.transpose(2, 0, 1)  # (n_batch, n_cameras, 2)
                mean_errors = np.linalg.norm(proj_2d_T - pts_batch, axis=2).mean(axis=1)  # (n_batch,)

                good_mask = mean_errors < config.target_reprojection_error
                good_global = batch_idx[good_mask]
                points_3d_flat[good_global] = p3d_batch[good_mask]
                weights_flat[good_global, :] = 1.0

                # For batch points above error threshold, use vectorized batch outlier rejection
                bad_local = np.where(~good_mask)[0]
                n_bad = len(bad_local)
                if n_bad > 0:
                    bad_global = batch_idx[bad_local]
                    p3d_rej, cam_w_rej = self._batch_outlier_rejection(
                        pts_batch=pts_batch[bad_local],
                        p3d_default=p3d_batch[bad_local],
                        default_mean_errors=mean_errors[bad_local],
                        config=config,
                    )
                    points_3d_flat[bad_global] = p3d_rej
                    weights_flat[bad_global, :] = cam_w_rej
            else:
                points_3d_flat[batch_idx] = p3d_batch
                weights_flat[batch_idx, :] = 1.0 / self.n_cameras

        # --- Per-point path: points with partial camera coverage ---
        for pt_idx in np.where(~all_cams_valid & (n_valid_per_pt >= config.minimum_cameras_for_triangulation))[0]:
            subp = und_flat[:, pt_idx, :]  # (n_cameras, 2)
            valid_idx = np.where(valid_all[:, pt_idx])[0]
            n_valid = len(valid_idx)
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

    def _batch_outlier_rejection(
            self,
            *,
            pts_batch: NDArray[np.float64],
            p3d_default: NDArray[np.float64],
            default_mean_errors: NDArray[np.float64],
            config: "TriangulationConfig",
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Vectorized subset-ensemble outlier rejection for P points simultaneously.

        Instead of calling triangulate_with_outlier_rejection() P times (one per
        failing keypoint), runs triangulate_simple_batch() once per camera
        combination — O(n_combos) SVD calls instead of O(P × n_combos).

        Args:
            pts_batch: (P, n_cameras, 2) undistorted-normalized coords, no NaNs.
            p3d_default: (P, 3) triangulated from all cameras.
            default_mean_errors: (P,) mean reprojection error for the default result.
            config: triangulation config (target_reprojection_error, max_drop, etc.)

        Returns:
            (points_3d, camera_weights): shapes (P, 3) and (P, n_cameras).
        """
        P = pts_batch.shape[0]
        n_cam = self.n_cameras
        target = config.target_reprojection_error
        min_cams = config.minimum_cameras_for_triangulation
        max_drop = config.maximum_cameras_to_drop

        # Initialise weighted ensemble accumulators using the default (all-cameras) result
        default_weights = np.exp(-5.0 * default_mean_errors / target)   # (P,)
        weighted_p3d_sum = p3d_default * default_weights[:, None]        # (P, 3)
        total_weight = default_weights.copy()                             # (P,)
        cam_weights_acc = np.full((P, n_cam), 0.0, dtype=np.float64)
        cam_weights_acc += default_weights[:, None]                      # broadcast (P, n_cam)

        best_p3d = p3d_default.copy()          # (P, 3)
        best_errors = default_mean_errors.copy()  # (P,)

        local_indices = list(range(n_cam))

        for drop_count in range(1, max_drop + 1):
            selected = n_cam - drop_count
            if selected < min_cams:
                break

            for combo in itertools.combinations(local_indices, selected):
                combo_arr = np.array(combo, dtype=np.intp)
                pts_sub = pts_batch[:, combo_arr, :]        # (P, selected, 2)
                ext_sub = self._extrinsics_mats[combo_arr]  # (selected, 3, 4)

                # Triangulate all P points for this camera subset in one SVD call
                p3d_sub = triangulate_simple_batch(
                    points_batch=pts_sub, extrinsics_mats=ext_sub
                )  # (P, 3)

                # Batch-project through subset cameras to get mean reprojection error per point
                hom = np.concatenate(
                    [p3d_sub, np.ones((P, 1), dtype=np.float64)], axis=1
                )  # (P, 4)
                proj = ext_sub @ hom.T   # (selected, 3, P)
                z = proj[:, 2, :]
                with np.errstate(invalid="ignore", divide="ignore"):
                    proj_2d = proj[:, :2, :] / z[:, None, :]   # (selected, 2, P)
                proj_2d_T = proj_2d.transpose(2, 0, 1)          # (P, selected, 2)
                mean_errs = np.linalg.norm(proj_2d_T - pts_sub, axis=2).mean(axis=1)  # (P,)

                # Accumulate weighted ensemble
                weights = np.exp(-5.0 * mean_errs / target)     # (P,)
                weighted_p3d_sum += p3d_sub * weights[:, None]
                total_weight += weights
                cam_weights_acc[:, combo_arr] += weights[:, None]

                # Update per-point best
                improved = mean_errs < best_errors
                best_p3d = np.where(improved[:, None], p3d_sub, best_p3d)
                best_errors = np.where(improved, mean_errs, best_errors)

        # Build output: weighted ensemble where weight > threshold, else best
        valid_w = total_weight > 1e-12
        safe_w = np.where(valid_w, total_weight, 1.0)
        weighted_p3d = np.where(valid_w[:, None], weighted_p3d_sum / safe_w[:, None], best_p3d)
        cam_weights = np.where(valid_w[:, None], cam_weights_acc / safe_w[:, None], 0.0)

        # If best never improved over default, revert to default with flat weights
        no_improvement = best_errors >= default_mean_errors
        weighted_p3d = np.where(no_improvement[:, None], p3d_default, weighted_p3d)
        cam_weights = np.where(no_improvement[:, None], 1.0, cam_weights)

        return weighted_p3d, cam_weights

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
        hom = np.concatenate(
            [points_3d_flat, np.ones((n_flat, 1), dtype=np.float64)], axis=1
        )  # (n_flat, 4)
        # _extrinsics_mats: (n_cameras, 3, 4); hom.T: (4, n_flat)
        proj = self._extrinsics_mats @ hom.T  # (n_cameras, 3, n_flat)
        z = proj[:, 2, :]  # (n_cameras, n_flat)
        with np.errstate(invalid="ignore", divide="ignore"):
            proj_2d = proj[:, :2, :] / z[:, None, :]  # (n_cameras, 2, n_flat)
        proj_2d = np.transpose(proj_2d, (0, 2, 1))  # (n_cameras, n_flat, 2)
        diff = data2d_normalized_flat - proj_2d  # (n_cameras, n_flat, 2)
        out = np.linalg.norm(diff, axis=2)  # (n_cameras, n_flat)
        nan_mask = (
            np.isnan(data2d_normalized_flat).any(axis=2)
            | np.isnan(points_3d_flat).any(axis=1)[None, :]
        )
        out[nan_mask] = np.nan
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
