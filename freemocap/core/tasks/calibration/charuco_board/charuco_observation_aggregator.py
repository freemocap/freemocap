"""Aggregates charuco observations for the anipose calibration path.

Collects CharucoObservation objects from skellytracker and converts them
directly to anipose row dicts via CharucoObservation.to_anipose_camera_row().
"""

from pydantic import BaseModel, Field, ConfigDict, Extra
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

CharucoObservations = dict[CameraIdString, CharucoObservation | None]


class CharucoObservationAggregator(BaseModel):
    """Collects CharucoObservation objects across frames per camera."""
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
    )
    anipose_camera_ordering: list[CameraIdString]
    individual_camera_observations: dict[CameraIdString, list[CharucoObservation]] = Field(
        default_factory=dict
    )

    @classmethod
    def from_charuco_observation_payload(
        cls,
        charuco_observations_by_camera: CharucoObservations,
        anipose_camera_ordering: list[CameraIdString],
    ) -> "CharucoObservationAggregator":
        if set(charuco_observations_by_camera.keys()) != set(anipose_camera_ordering):
            raise ValueError("charuco_observations_by_camera and anipose_camera_ordering must have the same camera ids")

        camera_observations: dict[CameraIdString, list[CharucoObservation]] = {}
        for camera_id, obs in charuco_observations_by_camera.items():
            if obs is None:
                raise ValueError(
                    "Cannot create CharucoObservationAggregator from payload with None observations "
                    "— use nan-filled CharucoObservation instead"
                )
            camera_observations[camera_id] = [obs]

        return cls(
            individual_camera_observations=camera_observations,
            anipose_camera_ordering=anipose_camera_ordering,
        )

    @property
    def all_observations_by_camera(self) -> dict[CameraIdString, list[CharucoObservation]]:
        return {cam_id: self.individual_camera_observations[cam_id] for cam_id in self.anipose_camera_ordering}

    def to_anipose_rows(self, n_corners: int) -> list[list[dict]]:
        """Convert stored observations to anipose row dicts for calibrate_rows()."""
        return [
            [obs.to_anipose_camera_row() for obs in self.individual_camera_observations[cam_id]]
            for cam_id in self.anipose_camera_ordering
        ]

    def add_observations(self, charuco_observations_by_camera: CharucoObservations) -> None:
        for camera_id, obs in charuco_observations_by_camera.items():
            if obs is None:
                raise ValueError(
                    "Cannot add None observations to CharucoObservationAggregator "
                    "— use nan-filled CharucoObservation instead"
                )
            self.individual_camera_observations[camera_id].append(obs)
