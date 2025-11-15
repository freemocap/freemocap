import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from freemocap.core.pipeline.posthoc_pipelines.posthoc_calibration_pipeline.calibration_helpers.freemocap_anipose import (
    AniposeCameraGroup
)

from  skellycam.core.types.type_overloads import  CameraIdString
from skellytracker.trackers.base_tracker.base_tracker_abcs import CharucoObservation

logger = logging.getLogger(__name__)


@dataclass
class TriangulatedObservationFrame:
    """Result of triangulating observations from multiple cameras."""
    frame_number: int
    points_3d: NDArray[np.float32]  # Shape: (n_points, 3)
    reprojection_error: NDArray[np.float32]  # Shape: (n_points,)
    reprojection_error_by_camera: NDArray[np.float32]  # Shape: (n_cameras, n_points)
    valid_points: NDArray[np.bool_]  # Shape: (n_points,) - mask of successfully triangulated points
    nan_mask: NDArray[np.bool_]  # Shape: (n_points,) - mask of points with NaN in any camera
    observations_by_camera: dict[str, 'CharucoObservation']  # Original observations for reference


@dataclass
class ObservationTriangulator:
    camera_group: AniposeCameraGroup
    use_ransac: bool = False
    min_cameras_for_triangulation: int = 2
    max_reprojection_error: float = 10.0
    min_cameras_with_detection: int = 2

    @property
    def camera_names(self) -> list[str]:
        return [cam.name for cam in self.camera_group.cameras]

    @property
    def n_cameras(self) -> int:
        return len(self.camera_group.cameras)

    @classmethod
    def create(
            cls,
            *,
            calibration_toml_path: str|Path,) -> 'ObservationTriangulator':
        camera_group = AniposeCameraGroup.load(str(calibration_toml_path))
        return cls(camera_group=camera_group)



    def triangulate_observations(
            self,
            *,
            observations_by_camera: dict[CameraIdString, CharucoObservation],
            frame_number: int | None = None,
    ) -> TriangulatedObservationFrame:
        """
        Triangulate observations from multiple synchronized cameras.

        Args:
            observations_by_camera: Dict mapping camera_id to BaseObservation instance
            frame_number: Optional frame number (will use observation's frame_number if not provided)

        Returns:
            TriangulatedObservationFrame with 3D points and metrics

        Raises:
            ValueError: If insufficient cameras or mismatched observations
        """
        if len(observations_by_camera) < self.min_cameras_for_triangulation:
            raise ValueError(
                f"Need at least {self.min_cameras_for_triangulation} cameras, "
                f"got {len(observations_by_camera)}"
            )

        # Extract frame number from first observation if not provided
        if frame_number is None:
            frame_number = next(iter(observations_by_camera.values())).frame_number

        # Verify all observations are from same frame
        frame_numbers = {obs.frame_number for obs in observations_by_camera.values()}
        if len(frame_numbers) > 1:
            raise ValueError(
                f"Observations from different frames: {frame_numbers}. "
                "All observations must be synchronized."
            )


        # Order according to calibration
        ordered_frames = self._order_observation_frames(observations_by_camera)

        # Stack 2D points and handle NaNs
        points_2d, nan_mask = self._stack_observations_with_nan_handling(ordered_frames)

        # Triangulate only points visible in enough cameras
        points_3d, reproj_error, reproj_error_by_cam = self._triangulate_with_nan_handling(
            points_2d=points_2d,
            nan_mask=nan_mask,
        )

        # Determine valid points
        valid_points = (~nan_mask) & (reproj_error < self.max_reprojection_error)

        return TriangulatedObservationFrame(
            frame_number=frame_number,
            points_3d=points_3d,
            reprojection_error=reproj_error,
            reprojection_error_by_camera=reproj_error_by_cam,
            valid_points=valid_points,
            nan_mask=nan_mask,
            observations_by_camera=observations_by_camera,
        )

    def _order_observation_frames(
            self,
            observations_by_camera: dict[CameraIdString, CharucoObservation],
    ) -> dict[CameraIdString, CharucoObservation]:
        """
        Order observation frames to match calibration camera order.

        Args:
            observations_by_camera: Unordered observation frames

        Returns:
            List of ObservationFrame2D ordered by calibration

        Raises:
            ValueError: If camera not found in calibration
        """
        ordered_observations: dict[CameraIdString, CharucoObservation | None] = {camera_id: None for camera_id in self.camera_names}
        found_cameras: set[CameraIdString] = set()

        for cam_name in self.camera_names:
            found = False
            for camera_id, observation in observations_by_camera.items():
                if cam_name in camera_id:
                    if camera_id in found_cameras:
                        raise ValueError(f"Duplicate camera data for {camera_id}")
                    ordered_observations[camera_id] = observation
                    found_cameras.add(camera_id)
                    found = True
                    break

            if not found:
                raise ValueError(
                    f"Camera {cam_name} from calibration not found in observations. "
                    f"Available cameras: {[camera_id for camera_id in observations_by_camera.keys()]} "
                    f"Expected cameras: {self.camera_names}"


                )

        if any(obs is None for obs in ordered_observations.values()):
            missing_cameras = [cam_id for cam_id, obs in ordered_observations.items() if obs is None]
            raise ValueError(f"Missing observations for cameras: {missing_cameras}")

        return ordered_observations

    def _stack_observations_with_nan_handling(
            self,
            ordered_frames: dict[CameraIdString,CharucoObservation],
    ) -> tuple[NDArray[np.float32], NDArray[np.bool_]]:
        """
        Stack 2D points from observations, handling NaNs for missing detections.

        Args:
            ordered_frames: Observation frames ordered by calibration

        Returns:
            Tuple of:
                - points_2d: Shape (n_cameras, n_points, 2) with NaNs preserved
                - nan_mask: Shape (n_points,) True where any camera has NaN

        Raises:
            ValueError: If observations have different numbers of points
        """
        # Get 2D points from each observation
        points_arrays = [frame.to_2d_array() for frame in ordered_frames.values()]

        # Verify all have same number of points
        n_points = points_arrays[0].shape[0]
        for i, points in enumerate(points_arrays[1:], 1):
            if points.shape[0] != n_points:
                raise ValueError(
                    f"Camera {ordered_frames[i].camera_id} has {points.shape[0]} points, "
                    f"expected {n_points} (from {ordered_frames[0].camera_id})"
                )

        # Stack into (n_cameras, n_points, 2)
        points_2d = np.stack(points_arrays, axis=0)

        # Find points that are NaN in any camera
        nan_mask_per_camera = np.any(np.isnan(points_2d), axis=2)  # (n_cameras, n_points)

        # Count how many cameras see each point
        cameras_per_point = np.sum(~nan_mask_per_camera, axis=0)  # (n_points,)

        # Mark points as invalid if not seen by enough cameras
        nan_mask = cameras_per_point < self.min_cameras_with_detection

        return points_2d, nan_mask

    def _triangulate_with_nan_handling(
            self,
            *,
            points_2d: NDArray[np.float32],
            nan_mask: NDArray[np.bool_],
    ) -> tuple[NDArray[np.float32], NDArray[np.float32], NDArray[np.float32]]:
        """
        Triangulate 2D points, handling NaN values appropriately.

        Args:
            points_2d: Shape (n_cameras, n_points, 2) potentially with NaNs
            nan_mask: Shape (n_points,) indicating invalid points

        Returns:
            Tuple of:
                - points_3d: Shape (n_points, 3) with NaNs for invalid points
                - reprojection_error: Shape (n_points,) with inf for invalid points
                - reprojection_error_by_camera: Shape (n_cameras, n_points)
        """
        n_cameras, n_points, _ = points_2d.shape

        # Initialize outputs
        points_3d = np.full((n_points, 3), np.nan, dtype=np.float32)
        reproj_error = np.full(n_points, np.inf, dtype=np.float32)
        reproj_error_by_camera = np.full((n_cameras, n_points), np.inf, dtype=np.float32)

        # Get indices of valid points
        valid_indices = np.where(~nan_mask)[0]

        if len(valid_indices) == 0:
            logger.warning("No valid points to triangulate")
            return points_3d, reproj_error, reproj_error_by_camera

        # Extract valid points for triangulation
        # For each valid point, we still need all camera views (even with NaNs)
        # Anipose should handle NaN values in the input
        points_2d_valid = points_2d[:, valid_indices, :]

        # Reshape for Anipose
        points_2d_flat = points_2d_valid.reshape(n_cameras, -1, 2)

        # Triangulate
        if self.use_ransac:
            points_3d_flat = self.camera_group.triangulate_ransac(
                points_2d_flat,
                progress=False,
                kill_event=None,
            )
        else:
            points_3d_flat = self.camera_group.triangulate(
                points_2d_flat,
                progress=False,
                kill_event=None,
            )

        if points_3d_flat is None:
            raise RuntimeError("Triangulation failed")

        # Calculate reprojection errors for valid points
        reproj_error_full = self.camera_group.reprojection_error(
            points_3d_flat, points_2d_flat
        )

        # Mean reprojection error per valid point
        reproj_error_valid = self.camera_group.calculate_mean_reprojection_error(
            reproj_error_full
        ).reshape(len(valid_indices))

        # Reprojection error by camera for valid points
        reproj_error_by_cam_valid = np.linalg.norm(
            reproj_error_full, axis=2
        ).reshape(n_cameras, len(valid_indices))

        # Place results back at correct indices
        points_3d[valid_indices] = points_3d_flat.reshape(len(valid_indices), 3)
        reproj_error[valid_indices] = reproj_error_valid
        reproj_error_by_camera[:, valid_indices] = reproj_error_by_cam_valid

        return points_3d, reproj_error, reproj_error_by_camera


