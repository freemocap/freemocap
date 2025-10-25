from pydantic import BaseModel, Field

from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.tasks.calibration_task.v1_capture_volume_calibration.anipose_camera_calibration.freemocap_anipose import \
    CameraGroup, AniposeCharucoBoard


CharucoObservations =  dict[CameraIdString, CharucoObservation | None]


class CharucoObservationAggregator(BaseModel):
    anipose_camera_ordering: list[CameraIdString]
    # anipose handles camera rows by the ordering of cameras in CameraGroup - so we need to use that ordering when we pass the camera rows to anipose
    individual_camera_rows: dict[CameraIdString, list] = Field(default_factory=dict)

    @classmethod
    def from_charuco_observation_payload(cls,
                                         charuco_observations_by_camera: CharucoObservations,
                                         anipose_camera_ordering: list[CameraIdString]):
        if set(charuco_observations_by_camera.keys()) != set(anipose_camera_ordering):
            raise ValueError("individual_camera_rows and anipose_camera_ordering must have the same camera ids")
        camera_rows = {}
        for camera_id, charuco_observation in charuco_observations_by_camera.items():
            anipose_camera_row = charuco_observation.to_anipose_camera_row() if charuco_observation is not None else None
            camera_rows[camera_id] = [anipose_camera_row] if anipose_camera_row is not None else []

        return cls(individual_camera_rows=camera_rows, anipose_camera_ordering=anipose_camera_ordering)

    @property
    def all_camera_rows(self):
        return [self.individual_camera_rows[anipose_camera_id] for anipose_camera_id in self.anipose_camera_ordering]

    def add_observations(self, charuco_observations_by_camera: CharucoObservations):
        for camera_id, charuco_observation in charuco_observations_by_camera.items():
            anipose_camera_row = charuco_observation.to_anipose_camera_row() if charuco_observation is not None else None
            if anipose_camera_row is not None:
                self.individual_camera_rows[camera_id].append(anipose_camera_row)


def  anipose_calibration_from_charuco_observations(charuco_observations_by_frame: list[CharucoObservations],
                                                   init_intrinsics=None,
                                                   init_extrinsics=None,
                                                   verbose: bool = True,
                                                   **kwargs):
    camera_group = CameraGroup()
    board = AniposeCharucoBoard()
    charuco_observation_aggregator: CharucoObservationAggregator | None = None
    for charuco_observations_by_camera in charuco_observations_by_frame:
        if charuco_observation_aggregator is None:
            charuco_observation_aggregator = CharucoObservationAggregator.from_charuco_observation_payload(
                charuco_observations_by_camera=charuco_observations_by_camera,
                anipose_camera_ordering=[camera.name for camera in camera_group.cameras])
        else:
            charuco_observation_aggregator.add_observations(charuco_observations_by_camera)

        all_camera_rows = charuco_observation_aggregator.all_camera_rows
        error = camera_group.calibrate_rows(all_camera_rows, board,
                                            init_intrinsics=init_intrinsics,
                                            init_extrinsics=init_extrinsics,
                                            verbose=verbose, **kwargs)