import logging

from pydantic import BaseModel, Field
from pydantic import model_validator
from skellycam.core.types.type_overloads import CameraIdString, FrameNumberInt
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.pubsub.pubsub_topics import CameraNodeOutputMessage
from freemocap.core.tasks.calibration_task.calibration_helpers.calibration_numpy_types import ImagePoint2D

CharucoObservations = dict[CameraIdString, CharucoObservation | None]

MultiFrameNumber = int
MINIMUM_CHARUCO_CORNERS_FOR_VISIBILITY:int=6
logger = logging.getLogger(__name__)

class CameraPair(BaseModel):
    base_camera_id: CameraIdString
    other_camera_id: CameraIdString

    @classmethod
    def from_ids(cls,*, base_camera_id: CameraIdString, other_camera_id: CameraIdString):
        return cls(base_camera_id=base_camera_id,
                   other_camera_id= other_camera_id)

    @model_validator(mode='after')
    def validate(self):
        if self.base_camera_id == self.other_camera_id:
            raise ValueError("base_camera_id and other_camera_id must be different")
        return self

    def __eq__(self, other):
        if isinstance(other, CameraPair):
            return self.model_dump() == other.model_dump()
        return False

    def __hash__(self):
        return hash(self.model_dump_json())


class CameraPairTargetView(BaseModel):
    multi_frame_number: MultiFrameNumber
    base_camera_id: CameraIdString
    other_camera_id: CameraIdString
    base_camera_observation: CharucoObservation
    other_camera_observation: CharucoObservation

    @model_validator(mode='after')
    def validate(self):
        if self.base_camera_id == self.other_camera_id:
            raise ValueError("base_camera_id and other_camera_id must be different")
        if self.base_camera_observation.frame_number != self.multi_frame_number:
            raise ValueError(
                f"base_camera_observation frame_number {self.base_camera_observation.frame_number} does not match multi_frame_number {self.multi_frame_number}")
        if self.other_camera_observation.frame_number != self.multi_frame_number:
            raise ValueError(
                f"other_camera_observation frame_number {self.other_camera_observation.frame_number} does not match multi_frame_number {self.multi_frame_number}")
        return self


class MultiCameraTargetView(BaseModel):
    multi_frame_number: MultiFrameNumber
    camera_node_output_by_camera: dict[CameraIdString, CameraNodeOutputMessage]

    @model_validator(mode='after')
    def validate(self):
        if not all([output.frame_number == self.multi_frame_number for output in
                    self.camera_node_output_by_camera.values()]):
            logger.warning(
                f"multi_frame_number {self.multi_frame_number} does not match all camera_node_output_by_camera multi_frame_numbers: {[output.frame_number for output in self.camera_node_output_by_camera.values()]}")
        return self

    @property
    def target_visibility_by_camera(self) -> dict[CameraIdString, bool]:
        visibility_by_camera = {}
        for camera_id, camera_node_output in self.camera_node_output_by_camera.items():
            visibility_by_camera[camera_id] = len(camera_node_output.charuco_observation.charuco_corners_dict) > MINIMUM_CHARUCO_CORNERS_FOR_VISIBILITY
        return visibility_by_camera

    @property
    def image_points_by_camera(self) -> dict[CameraIdString, list[ImagePoint2D]]:
        image_points_by_camera = {camera_id: [] for camera_id in self.camera_node_output_by_camera.keys()}
        for camera_id, camera_node_output in self.camera_node_output_by_camera.items():
            image_points_by_camera[camera_id].extend(
                list(camera_node_output.charuco_observation.detected_charuco_corners_in_full_array))

        return image_points_by_camera


class MultiCameraNodeOutputAccumulator(BaseModel):
    camera_ids: list[CameraIdString]
    multi_camera_views_by_frame:dict[FrameNumberInt,MultiCameraTargetView] = Field(default_factory=dict)
    camera_shared_views: dict[CameraIdString, dict[CameraPair, list[CameraPairTargetView]]]

    @classmethod
    def create(cls, camera_ids: list[CameraIdString]):
        camera_shared_views: dict[CameraIdString, dict[CameraPair, list[CameraPairTargetView]]] = {}
        for camera_id in camera_ids:
            for other_camera_id in camera_ids:
                if camera_id == other_camera_id:
                    continue
                if camera_id not in camera_shared_views:
                    camera_shared_views[camera_id] = {}
                pair = CameraPair.from_ids(base_camera_id=camera_id,
                                           other_camera_id=other_camera_id)
                camera_shared_views[camera_id][pair] = []
        return cls(camera_ids=camera_ids,
                   camera_shared_views=camera_shared_views)


    def receive_camera_node_output(
            self,
            multi_frame_number: int,
            camera_node_output_by_camera: dict[CameraIdString, CameraNodeOutputMessage]
    ):
        if multi_frame_number in self.multi_camera_views_by_frame:
            raise RuntimeError(f"Received duplicate camera node outputs for frame {multi_frame_number}")

        if set(camera_node_output_by_camera.keys()) != set(self.camera_ids):
            raise ValueError(
                f"camera_node_output_by_camera keys {camera_node_output_by_camera.keys()} do not match expected camera ids {self.camera_ids}")

        self.multi_camera_views_by_frame[multi_frame_number] = MultiCameraTargetView(
            multi_frame_number=multi_frame_number,
            camera_node_output_by_camera=camera_node_output_by_camera
        )

        # accumulate shared target views for each camera pair
        for camera_id in self.camera_shared_views.keys():
            if not camera_node_output_by_camera[camera_id].charuco_observation.charuco_board_visible:
                continue
            this_camera_obs = camera_node_output_by_camera[camera_id].charuco_observation
            for other_camera_id in self.camera_shared_views.keys():
                if camera_id == other_camera_id:
                    continue
                if not camera_node_output_by_camera[other_camera_id].charuco_observation.charuco_board_visible:
                    continue
                other_camera_obs = camera_node_output_by_camera[other_camera_id].charuco_observation
                pair = CameraPair.from_ids(base_camera_id=camera_id,
                                           other_camera_id=other_camera_id)
                target_view = CameraPairTargetView(
                    multi_frame_number=multi_frame_number,
                    base_camera_id=pair.base_camera_id,
                    other_camera_id=pair.other_camera_id,
                    base_camera_observation=this_camera_obs,
                    other_camera_observation=other_camera_obs
                )
                self.camera_shared_views[camera_id][pair].append(target_view)


    def get_shared_view_count_per_camera(self) -> dict[CameraIdString, int]:
        """
        Get the number of shared views for each camera id, i.e. the number of frames where the camera can see the target and at least one other camera can also see the target
        """
        #special case for single camera - all views with target visible are shared views
        if len(self.camera_ids) == 1:
            single_camera_id = self.camera_ids[0]
            visible_view_count = sum(1 for multi_camera_view in self.multi_camera_views_by_frame.values()
                                      if multi_camera_view.target_visibility_by_camera[single_camera_id])
            return {single_camera_id: visible_view_count}
        camera_shared_view_count = {camera_id: 0 for camera_id in self.camera_ids}
        for camera_id, pair_dict in self.camera_shared_views.items():
            for pair, target_views in pair_dict.items():
                camera_shared_view_count[camera_id] += len(target_views)

        return camera_shared_view_count

    def all_cameras_have_min_shared_views(self, min_shared_views: int = 500) -> bool:
        """
        find the total number of shared views for each camera id within the various camera pairs
        we don't need all possible pairs to have min_shared_views, just that each camera has min_shared_views with at least one other camera
        """
        return all([count >= min_shared_views for count in self.get_shared_view_count_per_camera().values()])


    def get_observations_by_camera(self, camera_id:CameraIdString) -> dict[FrameNumberInt, CharucoObservation]:
        """
        Get the charuco observations for a given camera id across all frames
        """
        observations_by_frame = {}
        for multi_frame_number, multi_camera_view in self.multi_camera_views_by_frame.items():
            camera_node_output = multi_camera_view.camera_node_output_by_camera[camera_id]
            observations_by_frame[multi_frame_number] = camera_node_output.charuco_observation
        return observations_by_frame



if __name__ == "__main__":
    mca =MultiCameraNodeOutputAccumulator.create(["CamA","CamB","CamC","CamD"])
    print(mca.model_dump_json(indent=2))