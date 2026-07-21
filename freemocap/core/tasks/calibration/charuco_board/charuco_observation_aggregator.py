"""Aggregates charuco observations for the anipose calibration path.

Collects Observation objects from skellytracker and converts them
to anipose row dicts via the new to_anipose_camera_row helper.
"""

from pydantic import BaseModel, Field, ConfigDict
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.core.data_primitives.observation import Observation
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition
from skellytracker.core.detectors.keypoint_detectors.charuco.anipose_export import to_anipose_camera_row

CharucoObservations = dict[CameraIdString, Observation | None]


class CharucoObservationAggregator(BaseModel):
    """Collects Observation objects across frames per camera."""
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )
    anipose_camera_ordering: list[CameraIdString]
    individual_camera_observations: dict[CameraIdString, list[Observation]] = Field(
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

        camera_observations: dict[CameraIdString, list[Observation]] = {}
        for camera_id, obs in charuco_observations_by_camera.items():
            if obs is None:
                raise ValueError(
                    "Cannot create CharucoObservationAggregator from payload with None observations "
                    "— use empty-stage Observation instead"
                )
            camera_observations[camera_id] = [obs]

        return cls(
            individual_camera_observations=camera_observations,
            anipose_camera_ordering=anipose_camera_ordering,
        )

    @property
    def all_observations_by_camera(self) -> dict[CameraIdString, list[Observation]]:
        return {cam_id: self.individual_camera_observations[cam_id] for cam_id in self.anipose_camera_ordering}

    def to_anipose_rows(self, n_corners: int, board_def: CharucoBoardDefinition) -> list[list[dict]]:
        """Convert stored observations to anipose row dicts for calibrate_rows()."""
        return [
            [
                to_anipose_camera_row(
                    keypoints=obs.stages["charuco"].keypoints,
                    board_def=board_def,
                    frame_number=obs.frame_number,
                )
                for obs in self.individual_camera_observations[cam_id]
                if "charuco" in obs.stages and obs.stages["charuco"].keypoints is not None
            ]
            for cam_id in self.anipose_camera_ordering
        ]

    def add_observations(self, charuco_observations_by_camera: CharucoObservations) -> None:
        for camera_id, obs in charuco_observations_by_camera.items():
            if obs is None:
                raise ValueError(
                    "Cannot add None observations to CharucoObservationAggregator "
                    "— use empty-stage Observation instead"
                )
            self.individual_camera_observations[camera_id].append(obs)
