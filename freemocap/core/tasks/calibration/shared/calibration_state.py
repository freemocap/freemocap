"""CalibrationStateTracker: wraps calibration with validity tracking.

Uses Triangulator (pure CameraModel-based DLT) instead of AniposeCameraGroup.
Provides optimistic loading, graceful degradation on repeated triangulation
failure, and periodic file-change detection for hot-reloading.
"""

import logging
import os
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseObservation

from freemocap.core.tasks.calibration.shared.calibration_models import CalibrationResult
from freemocap.core.tasks.calibration.shared.calibration_paths import get_last_successful_calibration_toml_path
from freemocap.core.tasks.calibration.shared.triangulator import Triangulator

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
                f"{len(cameras)} cameras: {[c.name for c in cameras]}"
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to load calibration from {path}: {e}", exc_info=True)
            return False

    def try_triangulate(
        self,
        *,
        frame_number: int,
        frame_observations_by_camera: dict[CameraIdString, BaseObservation],
        max_reprojection_error_px: float,
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

        try:
            calibration_camera_names = self._triangulator.camera_names

            # Collect named 2D points per calibration camera
            tracked_by_cam: dict[str, dict[str, NDArray[np.float64]]] = {}
            for cam_id, obs in frame_observations_by_camera.items():
                matched_name = _match_camera_name(
                    cam_id=cam_id,
                    calibration_camera_names=calibration_camera_names,
                )
                if matched_name is None:
                    continue
                tracked_by_cam[matched_name] = {
                    name: np.asarray(pt, dtype=np.float64)[:2]
                    for name, pt in obs.to_tracked_points().items()
                }

            if len(tracked_by_cam) < 2:
                return {}

            # Build subset triangulator if we don't have all cameras
            active_cam_names = sorted(tracked_by_cam.keys())
            if set(active_cam_names) != set(calibration_camera_names):
                sub_triangulator = Triangulator(
                    cameras=[
                        cam for cam in self._triangulator.cameras
                        if cam.name in tracked_by_cam
                    ]
                )
            else:
                sub_triangulator = self._triangulator
            ordered_cam_names: list[str] = sub_triangulator.camera_names
            n_cameras = len(ordered_cam_names)

            # Find all point names and count how many cameras see each
            all_point_names: set[str] = set()
            for pts in tracked_by_cam.values():
                all_point_names.update(pts.keys())

            # Keep only points visible in ≥2 cameras
            point_names: list[str] = sorted(
                name for name in all_point_names
                if sum(1 for cam in ordered_cam_names if name in tracked_by_cam[cam]) >= 2
            )

            if not point_names:
                return {}

            n_points = len(point_names)

            # Build (n_cameras, n_points, 2) array with NaN for missing observations
            stacked = np.full((n_cameras, n_points, 2), np.nan, dtype=np.float64)
            for cam_idx, cam_name in enumerate(ordered_cam_names):
                cam_points = tracked_by_cam[cam_name]
                for pt_idx, pt_name in enumerate(point_names):
                    if pt_name in cam_points:
                        stacked[cam_idx, pt_idx, :] = cam_points[pt_name]

            # Triangulate: (n_cameras, 1, n_points, 2) → (1, n_points, 3)
            triangulated = sub_triangulator.triangulate_array(
                data2d=stacked[:, np.newaxis, :, :],
            )
            points_3d = triangulated[0]  # (n_points, 3)

            # Reprojection error gate
            mean_reproj_error = sub_triangulator.mean_reprojection_error(
                points_3d=points_3d,
                points_2d=stacked,
            )  # (n_points,)
            bad_mask = mean_reproj_error > max_reprojection_error_px
            if np.any(bad_mask):
                points_3d[bad_mask] = np.nan

            # Build result dict, excluding NaN points
            result: dict[str, NDArray[np.float64]] = {}
            for i, name in enumerate(point_names):
                if not np.isnan(points_3d[i]).any():
                    result[name] = points_3d[i]

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
        # Preserve _calibration_file_mtime so we can detect when the file changes


def _match_camera_name(
    *,
    cam_id: CameraIdString,
    calibration_camera_names: list[str],
) -> str | None:
    """Match a runtime camera ID to a calibration camera name.

    Uses exact string matching only. Returns None (with a warning) if
    no match is found.
    """
    if cam_id in calibration_camera_names:
        return cam_id

    logger.warning(
        f"Camera '{cam_id}' has no exact match in calibration cameras "
        f"{calibration_camera_names} — skipping this camera for triangulation"
    )
    return None
