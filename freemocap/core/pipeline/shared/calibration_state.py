"""
CalibrationStateTracker: wraps AniposeCameraGroup with validity tracking.

Provides optimistic loading, graceful degradation on triangulation failure,
and explicit reload support (triggered by config updates after a posthoc
calibration completes).
"""
import logging
from pathlib import Path

from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseObservation
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pipeline.posthoc.posthoc_tasks.calibration_task import \
    get_last_successful_calibration_toml_path
from freemocap.core.pipeline.posthoc.posthoc_tasks.calibration_task import \
    AniposeCameraGroup
from freemocap.core.pipeline.posthoc.posthoc_tasks.mocap_task.mocap_helpers.triangulate_trajectory_array import \
    triangulate_frame_observations
from freemocap.core.types.type_overloads import TrackedPointNameString
from skellyforge.data_models.trajectory_3d import Point3d

logger = logging.getLogger(__name__)


class CalibrationStateTracker:
    """
    Tracks whether we have a valid calibration and provides safe triangulation.

    Lifecycle:
      1. On creation, optimistically try to load the latest calibration.
      2. Triangulation requests go through try_triangulate(), which returns
         None if no valid calibration is loaded.
      3. On triangulation failure, the calibration is invalidated — we stop
         trying until explicitly reloaded.
      4. reload() re-reads from disk (call after a posthoc calibration completes
         and the realtime pipeline receives a config update).
    """

    def __init__(self) -> None:
        self._anipose_camera_group: AniposeCameraGroup | None = None
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
        return self._is_valid and self._anipose_camera_group is not None

    @property
    def calibration_path(self) -> Path | None:
        return self._calibration_path if self._is_valid else None

    def reload(self) -> bool:
        """
        Try to load (or re-load) the latest calibration from disk.
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

            self._anipose_camera_group = AniposeCameraGroup.load(str(path))
            self._calibration_path = path
            self._is_valid = True
            self._failure_count = 0
            logger.info(f"Loaded calibration from {path}")
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
    ) -> dict[TrackedPointNameString, Point3d] | None:
        """
        Attempt triangulation with the current calibration.

        Returns the triangulated points dict, or None if:
          - No valid calibration is loaded
          - Triangulation failed (and the calibration is now invalidated)
        """
        if not self.is_valid:
            return None

        try:
            result = triangulate_frame_observations(
                frame_number=frame_number,
                frame_observations_by_camera=frame_observations_by_camera,
                anipose_camera_group=self._anipose_camera_group,
            )
            return result.to_point_dictionary() if result else {}

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
        self._anipose_camera_group = None
        self._calibration_path = None