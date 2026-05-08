"""CalibrationStateTracker: wraps calibration with validity tracking.

Uses Triangulator (pure CameraModel-based DLT) instead of AniposeCameraGroup.
Provides optimistic loading, graceful degradation on repeated triangulation
failure, and periodic file-change detection for hot-reloading.
"""

import logging
import os
import time
from pathlib import Path

from freemocap.core.pipeline.pipeline_stage_timer import PipelineStageTimer

import numpy as np
from numpy.typing import NDArray
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseObservation

from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from freemocap.core.tasks.calibration.shared.calibration_paths import get_last_successful_calibration_toml_path
from freemocap.core.tasks.calibration.shared.camera_id_resolution import resolve_camera_id_or_raise
from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig
from freemocap.core.tasks.triangulation.triangulator import Triangulator

logger = logging.getLogger(__name__)

# Invalidate calibration after this many consecutive triangulation failures
MAX_CONSECUTIVE_FAILURES: int = 10


class CalibrationStateTracker:
    """Tracks whether we have a valid calibration and provides safe triangulation.

    Uses the pure Triangulator (DLT from CameraModel) rather than AniposeCameraGroup.

    Lifecycle:
      1. On creation, optimistically try to load the latest calibration.
      2. Triangulation requests go through try_triangulate(), which returns
         None if no valid calibration is loaded.
      3. If triangulation fails repeatedly (MAX_CONSECUTIVE_FAILURES), the
         calibration is invalidated. A single bad frame does not kill 3D.
      4. check_for_update() polls the calibration file mtime and reloads
         if the file has changed. Existing calibration is preserved if the
         file is unchanged or if loading the new file fails.
    """

    def __init__(self) -> None:
        self._calibration: CalibrationResult | None = None
        self._triangulator: Triangulator | None = None
        self._is_valid: bool = False
        self._consecutive_failure_count: int = 0
        self._calibration_path: Path | None = None
        self._calibration_file_mtime: float | None = None
        # Maps frozenset of active calibration-name strings -> pre-built sub-Triangulator.
        # Lazily populated on first frame with a given camera subset; reused thereafter.
        self._subset_triangulator_cache: dict[frozenset, Triangulator] = {}
        # Maps runtime CameraIdString -> resolved calibration camera name.
        # Lazily populated. Cleared when the incoming camera ID set changes.
        self._cam_id_name_cache: dict[str, str] = {}
        # Last seen frozenset of incoming camera IDs, for detecting camera set changes.
        self._last_incoming_cam_ids: frozenset | None = None
        # self._timer = PipelineStageTimer(name="CalibrationStateTracker")

    @classmethod
    def create_and_try_load(cls) -> "CalibrationStateTracker":
        """Create a tracker and optimistically try to load the latest calibration."""
        tracker = cls()
        tracker._try_load_latest()
        return tracker

    @property
    def is_valid(self) -> bool:
        return self._is_valid and self._triangulator is not None

    @property
    def calibration_path(self) -> Path | None:
        return self._calibration_path

    def check_for_update(self) -> bool:
        """Check if the calibration file on disk has changed, and reload if so.

        Safe to call frequently (e.g. once per second). Does nothing if
        the file is unchanged or missing. Preserves existing calibration
        if the new file fails to load.

        Returns:
            True if a new calibration was loaded.
        """
        try:
            path = get_last_successful_calibration_toml_path()
            if not path.exists():
                return False
            mtime = os.path.getmtime(path)
            if mtime == self._calibration_file_mtime:
                return False
            logger.info(
                f"Calibration file changed on disk at {path} "
                f"(mtime={mtime}, previous_mtime={self._calibration_file_mtime})"
            )
            return self._try_load_from_path(path)
        except Exception as e:
            logger.debug(f"Error checking calibration file: {e}")
            return False

    def _try_load_latest(self) -> bool:
        """Try to load the most recent calibration file from the default path.

        Returns:
            True if calibration was loaded successfully.
        """
        try:
            path = get_last_successful_calibration_toml_path()
            if path.exists():
                logger.info(f"Found calibration file at {path}")
                return self._try_load_from_path(path)
            else:
                logger.debug(f"No calibration file found at {path}")
                return False
        except Exception as e:
            logger.debug(f"No existing calibration found: {e}")
            return False

    def _try_load_from_path(self, path: Path) -> bool:
        """Attempt to load calibration from an anipose-format TOML file.

        On success, replaces the current calibration state.
        On failure, logs the error and leaves the existing state untouched.

        Returns:
            True if calibration was loaded successfully.
        """
        try:
            calibration = CalibrationResult.load_anipose_toml(path)
            cameras = calibration.cameras
            triangulator = Triangulator(cameras=cameras)

            # Only swap state after everything succeeded
            self._triangulator = triangulator
            self._calibration = calibration
            self._calibration_path = path
            self._is_valid = True
            self._consecutive_failure_count = 0
            self._calibration_file_mtime = os.path.getmtime(path)
            logger.info(
                f"Loaded calibration from {path} with "
                f"{len(cameras)} cameras: {[c.id for c in cameras]}"
            )
            self._subset_triangulator_cache.clear()
            self._cam_id_name_cache.clear()
            self._last_incoming_cam_ids = None
            return True
        except Exception as e:
            logger.warning(f"Failed to load calibration from {path}: {e}", exc_info=True)
            return False

    def try_angulate(
        self,
        *,
        frame_number: int,
        frame_observations_by_camera: dict[CameraIdString, BaseObservation],
        max_reprojection_error_px: float,
        triangulation_config: TriangulationConfig | None = None,
    ) -> dict[str, NDArray[np.float64]] | None:
        """Attempt triangulation with reprojection error gating.

        Uses to_tracked_points() to get named 2D observations from each camera,
        finds points visible in ≥2 cameras, triangulates via DLT, and rejects
        points whose mean reprojection error exceeds max_reprojection_error_px.

        Returns the triangulated 3D points as a dict of {point_name: xyz},
        or None if no valid calibration is loaded or triangulation failed.
        """
        if not self.is_valid:
            return None

        if triangulation_config is None:
            triangulation_config = TriangulationConfig()

        try:
            calibration_camera_ids = self._triangulator.camera_ids

            # Detect when the incoming camera set changes (rare: reconnect, etc.)
            # and clear the name-resolution cache so stale entries don't linger.
            incoming_cam_ids: frozenset[str] = frozenset(frame_observations_by_camera.keys())
            if incoming_cam_ids != self._last_incoming_cam_ids:
                self._cam_id_name_cache.clear()
                self._last_incoming_cam_ids = incoming_cam_ids

            # Resolve runtime cam_id -> calibration camera name once per cam.
            matched_obs_by_cam: dict[str, BaseObservation] = {}
            for cam_id, obs in frame_observations_by_camera.items():
                if cam_id not in self._cam_id_name_cache:
                    self._cam_id_name_cache[cam_id] = _match_camera_name(
                        cam_id=cam_id,
                        calibration_camera_names=calibration_camera_ids,
                    )
                matched_obs_by_cam[self._cam_id_name_cache[cam_id]] = obs

            if len(matched_obs_by_cam) < 2:
                return {}

            # Reuse a cached sub-triangulator for this camera subset; only build
            # a new one when we see a novel active-camera combination.
            active_cam_set: frozenset[str] = frozenset(matched_obs_by_cam.keys())
            if active_cam_set == frozenset(calibration_camera_ids):
                sub_triangulator = self._triangulator
            elif active_cam_set in self._subset_triangulator_cache:
                sub_triangulator = self._subset_triangulator_cache[active_cam_set]
            else:
                sub_triangulator = Triangulator(
                    cameras=[
                        cam for cam in self._triangulator.cameras
                        if cam.id in matched_obs_by_cam
                    ]
                )
                self._subset_triangulator_cache[active_cam_set] = sub_triangulator
            ordered_cam_names: list[str] = sub_triangulator.camera_ids
            n_cameras = len(ordered_cam_names)

            # Fast path: when every observation type uses the canonical
            # PointCloud-only `to_tracked_points` (i.e. doesn't add any extra
            # named points beyond `obs.points`), and all cameras share the same
            # PointCloud names tuple, we can stack `xyz[:, :2]` arrays directly
            # and skip per-keypoint dict construction. RTMPose hits this path.
            ordered_obs: list[BaseObservation] = [
                matched_obs_by_cam[c] for c in ordered_cam_names
            ]
            first_obs = ordered_obs[0]
            canonical_names: tuple[str, ...] = first_obs.points.names
            fast_path = (
                type(first_obs).to_tracked_points is BaseObservation.to_tracked_points
                and all(
                    type(o).to_tracked_points is BaseObservation.to_tracked_points
                    and o.points.names == canonical_names
                    for o in ordered_obs[1:]
                )
            )

            _t0 = time.perf_counter()
            if fast_path:
                # Build (n_cameras, n_points, 2) by stacking xy slices.
                stacked = np.stack(
                    [np.ascontiguousarray(o.points.xy, dtype=np.float64) for o in ordered_obs]
                )
                point_names_seq: tuple[str, ...] = canonical_names
                # Filter to points visible in ≥2 cameras
                visible_per_point = (~np.isnan(stacked[..., 0])).sum(axis=0)
                keep_mask = visible_per_point >= 2
                if not bool(keep_mask.any()):
                    return {}
                if not bool(keep_mask.all()):
                    stacked = stacked[:, keep_mask, :]
                    point_names_seq = tuple(
                        n for n, k in zip(canonical_names, keep_mask.tolist()) if k
                    )
            else:
                # Fallback for observations whose `to_tracked_points` adds extra
                # named points (e.g. CharucoObservation injects per-aruco-corner
                # entries). Original dict-based assembly.
                tracked_by_cam: dict[str, dict[str, NDArray[np.float64]]] = {
                    cam_name: {
                        name: np.asarray(pt, dtype=np.float64)[:2]
                        for name, pt in matched_obs_by_cam[cam_name].to_tracked_points().items()
                    }
                    for cam_name in ordered_cam_names
                }
                all_point_names: set[str] = set()
                for pts in tracked_by_cam.values():
                    all_point_names.update(pts.keys())
                point_names_list: list[str] = sorted(
                    name for name in all_point_names
                    if sum(1 for cam in ordered_cam_names if name in tracked_by_cam[cam]) >= 2
                )
                if not point_names_list:
                    return {}
                point_names_seq = tuple(point_names_list)
                stacked = np.full(
                    (n_cameras, len(point_names_seq), 2), np.nan, dtype=np.float64
                )
                for cam_idx, cam_name in enumerate(ordered_cam_names):
                    cam_points = tracked_by_cam[cam_name]
                    for pt_idx, pt_name in enumerate(point_names_seq):
                        if pt_name in cam_points:
                            stacked[cam_idx, pt_idx, :] = cam_points[pt_name]
            # self._timer.record("build_stacked", (time.perf_counter() - _t0) * 1e3)

            # Triangulate the single frame
            _t0 = time.perf_counter()
            triangulation_result = sub_triangulator.triangulate(
                data2d=stacked,
                config=triangulation_config,
            )
            points_3d = triangulation_result.points_3d  # (n_points, 3)
#             self._timer.record("triangulate", (time.perf_counter() - _t0) * 1e3)

            # Reprojection error gate (in pixels, mean across valid cameras)
            _t0 = time.perf_counter()
            mean_reproj_error = sub_triangulator.mean_reprojection_error(
                points_3d=points_3d,
                points_2d_pixel=stacked,
            )  # (n_points,)
            bad_mask = mean_reproj_error > max_reprojection_error_px
            if np.any(bad_mask):
                points_3d[bad_mask] = np.nan
#             self._timer.record("mean_reproj_error", (time.perf_counter() - _t0) * 1e3)

            # Build result dict, excluding NaN points
            _t0 = time.perf_counter()
            valid_pt_mask = ~np.isnan(points_3d).any(axis=1)
            result: dict[str, NDArray[np.float64]] = {
                name: points_3d[i]
                for i, name in enumerate(point_names_seq)
                if valid_pt_mask[i]
            }
#             self._timer.record("result_dict", (time.perf_counter() - _t0) * 1e3)
#             self._timer.maybe_report()

            # Triangulation succeeded — reset failure counter
            self._consecutive_failure_count = 0
            return result

        except Exception as e:
            self._consecutive_failure_count += 1
            if self._consecutive_failure_count >= MAX_CONSECUTIVE_FAILURES:
                logger.error(
                    f"Triangulation failed {self._consecutive_failure_count} times "
                    f"consecutively — invalidating calibration. Last error: {e}",
                    exc_info=True,
                )
                self._invalidate()
            else:
                logger.warning(
                    f"Triangulation failed (failure "
                    f"{self._consecutive_failure_count}/{MAX_CONSECUTIVE_FAILURES}): {e}",
                )
            return None

    def _invalidate(self) -> None:
        self._is_valid = False
        self._triangulator = None
        self._calibration = None
        self._calibration_path = None
        self._subset_triangulator_cache.clear()
        self._cam_id_name_cache.clear()
        self._last_incoming_cam_ids = None
        # Preserve _calibration_file_mtime so we can detect when the file changes


def _match_camera_name(
    *,
    cam_id: CameraIdString,
    calibration_camera_names: list[str],
) -> str:
    """Match a runtime camera_id to a calibration camera name.

    Uses exact equality first, then the same fallback ladder as the
    SkellyCam video filename parser (cam-prefix, trailing-int, opaque
    digit). Raises `CameraIdMismatchError` (a `KeyError`) on miss — the
    caller's existing exception handling treats this as a triangulation
    failure that increments the consecutive-failure counter.
    """
    return resolve_camera_id_or_raise(
        cam_id,
        calibration_camera_names,
        context="runtime frame camera_id vs calibration TOML",
    )
