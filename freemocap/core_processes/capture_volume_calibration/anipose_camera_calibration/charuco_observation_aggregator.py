from pydantic import BaseModel, Field

from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation
from skellycam.core.types.type_overloads import CameraIdString

class CharucoObservationPayload(BaseModel):
    charuco_observations: dict[CameraIdString, CharucoObservation | None]

class CharucoObservationAggregator(BaseModel):
    anipose_camera_ordering: list[CameraIdString]
    # anipose handles camera rows by the ordering of cameras in CameraGroup - so we need to use that ordering when we pass the camera rows to anipose
    individual_camera_rows: dict[CameraIdString, list] = Field(default_factory=dict)

    @classmethod
    def from_charuco_observation_payload(cls, charuco_observation_payload: CharucoObservationPayload, anipose_camera_ordering: list[CameraIdString]):
        if set(charuco_observation_payload.charuco_observations.keys()) != set(anipose_camera_ordering):
            raise ValueError("individual_camera_rows and anipose_camera_ordering must have the same camera ids")
        camera_rows = {}
        for camera_id, charuco_observation in charuco_observation_payload.charuco_observations.items():
            anipose_camera_row = charuco_observation.to_anipose_camera_row() if charuco_observation is not None else None
            camera_rows[camera_id] = [anipose_camera_row] if anipose_camera_row is not None else []
            
        return cls(individual_camera_rows=camera_rows, anipose_camera_ordering=anipose_camera_ordering)
    
    @property
    def all_camera_rows(self):
        return [self.individual_camera_rows[anipose_camera_id] for anipose_camera_id in self.anipose_camera_ordering]

    def add_observations(self, charuco_observation_payload: CharucoObservationPayload):
        for camera_id, charuco_observation in charuco_observation_payload.charuco_observations.items():
            anipose_camera_row = charuco_observation.to_anipose_camera_row() if charuco_observation is not None else None
            if anipose_camera_row is not None:
                self.individual_camera_rows[camera_id].append(anipose_camera_row)
