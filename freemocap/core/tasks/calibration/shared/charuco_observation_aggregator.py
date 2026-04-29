"""Aggregates charuco observations into structured CharucoCornersObservation objects.

Used by the anipose calibration path. Anipose row dicts are produced on demand
via to_anipose_rows(), keeping the anipose format an output-only detail.
"""

import numpy as np
from pydantic import BaseModel, Field
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.core.tasks.calibration.shared.calibration_models import (
    CharucoCornersObservation,
    CornerObservation,
)


def charuco_observation_to_corners_observation(
    obs: CharucoObservation,
    camera_name: str,
) -> CharucoCornersObservation:
    """Convert a skellytracker CharucoObservation to the shared CharucoCornersObservation."""
    if obs.charuco_empty or obs.detected_charuco_corner_ids is None:
        return CharucoCornersObservation(camera_name=camera_name, frame_index=obs.frame_number, corners=[])

    corners = []
    for cid, xy in zip(
        obs.detected_charuco_corner_ids.ravel(),
        obs.detected_charuco_corners_image_coordinates,
    ):
        corners.append(CornerObservation(corner_id=int(cid), pixel_xy=xy.ravel()[:2]))

    return CharucoCornersObservation(camera_name=camera_name, frame_index=obs.frame_number, corners=corners)


def charuco_corners_observation_to_anipose_row(
    obs: CharucoCornersObservation,
    n_corners: int,
) -> dict:
    """Convert a CharucoCornersObservation to the anipose row dict format expected by calibrate_rows()."""
    filled = np.full((n_corners, 1, 2), np.nan, dtype=np.float64)
    for corner in obs.corners:
        filled[corner.corner_id, 0, :] = corner.pixel_xy

    if obs.corners:
        corners = np.array([c.pixel_xy for c in obs.corners], dtype=np.float64).reshape(-1, 1, 2)
        ids = np.array([c.corner_id for c in obs.corners], dtype=np.int32).reshape(-1, 1)
    else:
        corners = np.empty((0, 1, 2), dtype=np.float64)
        ids = np.empty((0, 1), dtype=np.int32)

    return {"framenum": (0, obs.frame_index), "corners": corners, "ids": ids, "filled": filled}

CharucoObservations = dict[CameraIdString, CharucoObservation | None]


class CharucoObservationAggregator(BaseModel):
    """Collects charuco observations across frames, stored as CharucoCornersObservation."""

    anipose_camera_ordering: list[CameraIdString]
    individual_camera_observations: dict[CameraIdString, list[CharucoCornersObservation]] = Field(
        default_factory=dict
    )

    @classmethod
    def from_charuco_observation_payload(
        cls,
        charuco_observations_by_camera: CharucoObservations,
        anipose_camera_ordering: list[CameraIdString],
    ) -> "CharucoObservationAggregator":
        if set(charuco_observations_by_camera.keys()) != set(anipose_camera_ordering):
            raise ValueError("individual_camera_observations and anipose_camera_ordering must have the same camera ids")



        camera_observations: dict[CameraIdString, list[CharucoCornersObservation]] = {}
        for camera_id, charuco_observation in charuco_observations_by_camera.items():
            if charuco_observation is None:
                raise ValueError(
                    "Cannot create CharucoObservationAggregator from payload with None observations "
                    "— use nan-filled CharucoObservation instead"
                )
            corners_obs = charuco_observation_to_corners_observation(charuco_observation, camera_name=camera_id)
            camera_observations[camera_id] = [corners_obs]

        return cls(individual_camera_observations=camera_observations, anipose_camera_ordering=anipose_camera_ordering)

    @property
    def all_observations_by_camera(self) -> dict[CameraIdString, list[CharucoCornersObservation]]:
        """Ordered access to stored observations per camera."""
        return {cam_id: self.individual_camera_observations[cam_id] for cam_id in self.anipose_camera_ordering}

    def to_anipose_rows(self, n_corners: int) -> list[list[dict]]:
        """Convert stored observations to anipose row dicts for calibrate_rows()."""

        return [
            [charuco_corners_observation_to_anipose_row(obs, n_corners=n_corners)
             for obs in self.individual_camera_observations[cam_id]]
            for cam_id in self.anipose_camera_ordering
        ]

    def add_observations(self, charuco_observations_by_camera: CharucoObservations) -> None:

        for camera_id, charuco_observation in charuco_observations_by_camera.items():
            if charuco_observation is None:
                raise ValueError(
                    "Cannot add None observations to CharucoObservationAggregator "
                    "— use nan-filled CharucoObservation instead"
                )
            corners_obs = charuco_observation_to_corners_observation(charuco_observation, camera_name=camera_id)
            self.individual_camera_observations[camera_id].append(corners_obs)
