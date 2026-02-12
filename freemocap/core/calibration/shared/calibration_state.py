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
      3. On triangulation failure, the calibration is invalidated — we stop
         trying until explicitly reloaded.
      4. reload() re-reads from disk (call after a posthoc calibration completes).
    """

    def __init__(self) -> None:
        self._triangulator: Triangulator | None = None
        self._calibration: CalibrationResult | None = None
        self._is_valid: bool = False
        self._calibration_path: Path | None = None
        self._failure_count: int = 0

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

    @property
    def calibration(self) -> CalibrationResult | None:
        return self._calibration if self._is_valid else None

    @property
    def triangulator(self) -> Triangulator | None:
        return self._triangulator if self._is_valid else None

    def reload(self) -> bool:
        """Try to load (or re-load) the latest calibration from disk.

        Returns True if a valid calibration was loaded.
        """
        try:
            path = get_last_successful_calibration_toml_path()
            if path is None:
                logger.debug("No calibration file found on disk")
                self._invalidate()
                return False

            path = Path(str(path))
            if not path.exists():
                logger.debug(f"Calibration path does not exist: {path}")
                self._invalidate()
                return False

            calibration = CalibrationResult.load_anipose_toml(path)
            if len(calibration.cameras) == 0:
                raise ValueError(
                    f"Calibration file at {path} contains no cameras — "
                    f"file may be corrupt or incomplete"
                )

            triangulator = Triangulator.from_calibration_result(calibration=calibration)

            self._calibration = calibration
            self._triangulator = triangulator
            self._calibration_path = path
            self._is_valid = True
            self._failure_count = 0
            logger.info(
                f"Loaded calibration from {path} with cameras: {triangulator.camera_names}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to load calibration: {e}", exc_info=True)
            self._invalidate()
            return False

    def try_triangulate(
        self,
        *,
        frame_number: int,
        frame_observations_by_camera: dict[CameraIdString, BaseObservation],
    ) -> dict[str, NDArray[np.float64]] | None:
        """Attempt triangulation with the current calibration.

        Returns the triangulated 3D points as a dict of {point_name: xyz},
        or None if no valid calibration is loaded or triangulation failed.
        """
        if not self.is_valid:
            return None

        try:
            # Stack 2D observations from all cameras in triangulator order
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
                logger.debug(
                    f"Frame {frame_number}: only {len(data_by_cam)} cameras matched, need >= 2"
                )
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
            n_points = next(iter(data_by_cam.values())).shape[0]
            stacked = np.stack(
                [data_by_cam[name] for name in ordered_names],
                axis=0,
            )  # (n_cameras, n_points, 2)

            # Add frame dimension
            stacked = stacked[:, np.newaxis, :, :]  # (n_cameras, 1, n_points, 2)

            triangulated = sub_triangulator.triangulate_array(data2d=stacked)
            # triangulated shape: (1, n_points, 3)
            points_3d = triangulated[0]  # (n_points, 3)

            # Rotate 180 deg about X (freemocap convention)
            rotation_matrix = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]])
            points_3d = points_3d @ rotation_matrix.T

            # Build point name dict from first observation
            first_obs = next(iter(frame_observations_by_camera.values()))
            point_names = list(first_obs.to_tracked_points().keys())

            result: dict[str, NDArray[np.float64]] = {}
            for i, name in enumerate(point_names):
                if i < points_3d.shape[0]:
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
