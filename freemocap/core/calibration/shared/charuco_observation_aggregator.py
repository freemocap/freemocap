"""Aggregates charuco observations into anipose-compatible row format.

Used only by the anipose calibration path.
"""

from pydantic import BaseModel, Field
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

CharucoObservations = dict[CameraIdString, CharucoObservation | None]


class CharucoObservationAggregator(BaseModel):
    """Collects charuco observations across frames into anipose row format."""

    anipose_camera_ordering: list[CameraIdString]
    individual_camera_rows: dict[CameraIdString, list] = Field(default_factory=dict)

    @classmethod
    def from_charuco_observation_payload(
        cls,
        charuco_observations_by_camera: CharucoObservations,
        anipose_camera_ordering: list[CameraIdString],
    ) -> "CharucoObservationAggregator":
        if set(charuco_observations_by_camera.keys()) != set(anipose_camera_ordering):
            raise ValueError("individual_camera_rows and anipose_camera_ordering must have the same camera ids")

        camera_rows: dict[CameraIdString, list] = {}
        for camera_id, charuco_observation in charuco_observations_by_camera.items():
            if charuco_observation is None:
                raise ValueError(
                    "Cannot create CharucoObservationAggregator from payload with None observations "
                    "— use nan-filled CharucoObservation instead"
                )
            anipose_camera_row = charuco_observation.to_anipose_camera_row()
            if anipose_camera_row is None:
                raise ValueError(
                    "Cannot create CharucoObservationAggregator from payload with None anipose row "
                    "— use nan-filled CharucoObservation instead"
                )
            camera_rows[camera_id] = [anipose_camera_row]

        return cls(individual_camera_rows=camera_rows, anipose_camera_ordering=anipose_camera_ordering)

    @property
    def all_camera_rows(self) -> list[list]:
        return [self.individual_camera_rows[cam_id] for cam_id in self.anipose_camera_ordering]

    def add_observations(self, charuco_observations_by_camera: CharucoObservations) -> None:
        for camera_id, charuco_observation in charuco_observations_by_camera.items():
            if charuco_observation is None:
                raise ValueError(
                    "Cannot add None observations to CharucoObservationAggregator "
                    "— use nan-filled CharucoObservation instead"
                )
            anipose_camera_row = charuco_observation.to_anipose_camera_row()
            if anipose_camera_row is None:
                raise ValueError(
                    "Cannot add None anipose row to CharucoObservationAggregator "
                    "— use nan-filled CharucoObservation instead"
                )
            self.individual_camera_rows[camera_id].append(anipose_camera_row)
