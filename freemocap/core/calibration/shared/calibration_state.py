"""CalibrationStateTracker: wraps calibration with validity tracking.

Uses Triangulator (pure CameraModel-based DLT) instead of AniposeCameraGroup.
Provides optimistic loading, graceful degradation on triangulation failure,
and explicit reload support.
"""

import logging
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseObservation

from freemocap.core.calibration.shared.calibration_models import CalibrationResult
from freemocap.core.calibration.shared.calibration_paths import get_last_successful_calibration_toml_path
from freemocap.core.calibration.shared.triangulator import Triangulator

logger = logging.getLogger(__name__)


class CalibrationStateTracker:
    """Tracks whether we have a valid calibration and provides safe triangulation.

    Uses the pure Triangulator (DLT from CameraModel) rather than AniposeCameraGroup.

    Lifecycle:
      1. On creation, optimistically try to load the latest calibration.
      2. Triangulation requests go through try_triangulate(), which returns
         None if no valid calibration is loaded.
      3. If triangulation fails, the calibration is invalidated and all
         subsequent calls return None until reload() is called.
      4. reload() can be called after a new calibration is saved to disk.
    """

    def __init__(self, data_folder: str | Path | None = None):
        self._data_folder = Path(data_folder) if data_folder else None
        self._calibration: CalibrationResult | None = None
        self._triangulator: Triangulator | None = None
        self._is_valid = False
        self._failure_count = 0
        self._calibration_path: Path | None = None

        if self._data_folder:
            self._try_load_latest()
    @classmethod
    def create_and_try_load(cls) -> "CalibrationStateTracker":
        """Create a tracker and optimistically try to load the latest calibration."""
        tracker = cls()
        tracker.reload()
        return tracker

    @property
    def is_valid(self) -> bool:
        return self._is_valid and self._triangulator is not None

    @property
    def calibration_path(self) -> Path | None:
        return self._calibration_path if self._is_valid else None

    def _try_load_latest(self) -> None:
        """Try to load the most recent calibration file."""
        try:
            path = get_last_successful_calibration_toml_path(self._data_folder)
            if path and path.exists():
                self._load_from_path(path)
        except Exception as e:
            logger.debug(f"No existing calibration found: {e}")

    def _load_from_path(self, path: Path) -> None:
        """Load calibration from a TOML file."""
        try:
            calibration = CalibrationResult.from_toml(path)
            cameras = calibration.to_camera_models()
            self._triangulator = Triangulator(cameras=cameras)
            self._calibration = calibration
            self._calibration_path = path
            self._is_valid = True
            self._failure_count = 0
            logger.info(
                f"Loaded calibration from {path} with "
                f"{len(cameras)} cameras: {[c.name for c in cameras]}"
            )
        except Exception as e:
            logger.warning(f"Failed to load calibration from {path}: {e}")
            self._invalidate()

    @property
    def is_valid(self) -> bool:
        return self._is_valid

    @property
    def calibration_path(self) -> Path | None:
        return self._calibration_path

    def reload(self, path: Path | None = None) -> bool:
        """Reload calibration from disk.

        Args:
            path: Explicit path, or None to re-discover latest.

        Returns:
            True if calibration was loaded successfully.
        """
        self._invalidate()
        if path:
            self._load_from_path(path)
        elif self._data_folder:
            self._try_load_latest()
        return self._is_valid

    def try_triangulate(
        self,
        *,
        frame_number: int,
        frame_observations_by_camera: dict[CameraIdString, BaseObservation],
        max_reprojection_error_px: float,
    ) -> dict[str, NDArray[np.float64]] | None:
        """Attempt triangulation with reprojection error gating.

        After DLT triangulation, each 3D point is reprojected into all cameras.
        Points whose mean reprojection error exceeds max_reprojection_error_px
        are replaced with NaN (and excluded from the returned dict).

        Returns the triangulated 3D points as a dict of {point_name: xyz},
        or None if no valid calibration is loaded or triangulation failed.
        """
        if not self.is_valid:
            return None

        try:
            # Stack 2D observations from all cameras in triangulator order.
            # Each BaseObservation.to_2d_array() returns (n_points, 2)
            camera_names = self._triangulator.camera_names
            data_by_cam: dict[str, NDArray[np.float64]] = {}

            for cam_id, obs in frame_observations_by_camera.items():
                # Match camera ID to calibration camera name
                matched_name: str | None = None
                for cal_name in camera_names:
                    if cal_name == cam_id or cal_name in cam_id or cam_id in cal_name:
                        matched_name = cal_name
                        break

                if matched_name is None:
                    logger.warning(
                        f"Camera '{cam_id}' not found in calibration cameras {camera_names}, skipping"
                    )
                    continue

                arr_2d = obs.to_2d_array()
                data_by_cam[matched_name] = arr_2d[..., :2]

            if len(data_by_cam) < 2:
                return {}

            # Build subset triangulator if we don't have all cameras
            if set(data_by_cam.keys()) != set(camera_names):
                sub_triangulator = Triangulator(
                    cameras=[
                        cam for cam in self._triangulator.cameras
                        if cam.name in data_by_cam
                    ]
                )
            else:
                sub_triangulator = self._triangulator

            # Stack into (n_cameras, 1, n_points, 2)
            ordered_names = sub_triangulator.camera_names
            stacked = np.stack(
                [data_by_cam[name] for name in ordered_names],
                axis=0,
            )  # (n_cameras, n_points, 2)

            stacked = stacked[:, np.newaxis, :, :]  # (n_cameras, 1, n_points, 2)

            triangulated = sub_triangulator.triangulate_array(data2d=stacked)
            # triangulated shape: (1, n_points, 3)
            points_3d = triangulated[0]  # (n_points, 3)

            # --- Reprojection error gate ---
            stacked_2d = stacked[:, 0, :, :]
            mean_reproj_error = sub_triangulator.mean_reprojection_error(
                points_3d=points_3d,
                points_2d=stacked_2d,
            )  # (n_points,)

            bad_mask = mean_reproj_error > max_reprojection_error_px
            n_rejected = int(np.sum(bad_mask))
            if n_rejected > 0:
                points_3d[bad_mask] = np.nan

            # Rotate 180 deg about X (freemocap convention)
            rotation_matrix = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]])
            points_3d = points_3d @ rotation_matrix.T

            # Get point names from the PointCloud — structurally guaranteed
            # to match to_2d_array() row order because both read from the
            # same PointCloud. This replaces the old to_tracked_points().keys()
            # pattern which could desync when NaN filtering was inconsistent.
            first_obs = next(iter(frame_observations_by_camera.values()))
            point_names: tuple[str, ...] = first_obs.points.names

            result: dict[str, NDArray[np.float64]] = {}
            for i, name in enumerate(point_names):
                if i < points_3d.shape[0] and not np.isnan(points_3d[i]).any():
                    result[name] = points_3d[i]

            return result

        except Exception as e:
            self._failure_count += 1
            logger.warning(
                f"Triangulation failed (failure #{self._failure_count}): {e} "
                f"— invalidating calibration",
                exc_info=True,
            )
            self._invalidate()
            return None

    def _invalidate(self) -> None:
        self._is_valid = False
        self._triangulator = None
        self._calibration = None
        self._calibration_path = None