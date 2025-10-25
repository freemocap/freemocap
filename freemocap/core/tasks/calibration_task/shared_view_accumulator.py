import logging

from pydantic import BaseModel, Field
from pydantic import model_validator
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.core.pubsub.pubsub_topics import CameraNodeOutputMessage
from freemocap.core.tasks.calibration_task.calibration_helpers.calibration_numpy_types import ImagePoint2D

CharucoObservations = dict[CameraIdString, CharucoObservation | None]

MultiFrameNumber = int

logger = logging.getLogger(__name__)

class CameraPair(BaseModel):
    base_camera_id: CameraIdString
    other_camera_id: CameraIdString

    @classmethod
    def from_ids(cls, base_camera_id: CameraIdString, other_camera_id: CameraIdString):
        return cls(base_camera_id=min(base_camera_id, other_camera_id),
                   other_camera_id=max(base_camera_id, other_camera_id))

    @model_validator(mode='after')
    def validate(self):
        if self.base_camera_id == self.other_camera_id:
            raise ValueError("base_camera_id and other_camera_id must be different")
        if not (self.base_camera_id < self.other_camera_id):
            raise ValueError("base_camera_id must be less than other_camera_id")
        return self

    def __eq__(self, other):
        if isinstance(other, CameraPair):
            return self.model_dump() == other.model_dump()
        return False

    def __hash__(self):
        # Use a frozenset to ensure hashability and use this model as a key in a dictionary
        return hash(frozenset(self.model_dump().items()))


class CameraPairTargetView(BaseModel):
    multi_frame_number: MultiFrameNumber
    camera_pair: CameraPair
    camera_node_output_by_camera: dict[CameraIdString, CameraNodeOutputMessage]

    @model_validator(mode='after')
    def validate(self):
        if not self.camera_pair.base_camera_id in self.camera_node_output_by_camera:
            raise ValueError(
                f"base_camera_id {self.camera_pair.base_camera_id} not in camera_node_output_by_camera keys {self.camera_node_output_by_camera.keys()}")
        if not self.camera_pair.other_camera_id in self.camera_node_output_by_camera:
            raise ValueError(
                f"other_camera_id {self.camera_pair.other_camera_id} not in camera_node_output_by_camera keys {self.camera_node_output_by_camera.keys()}")
        return self


class MultiCameraTargetView(BaseModel):
    multi_frame_number: MultiFrameNumber
    camera_node_output_by_camera: dict[CameraIdString, CameraNodeOutputMessage]

    @model_validator(mode='after')
    def validate(self):
        if len(self.camera_node_output_by_camera) < 2:
            raise ValueError(
                f"camera_node_output_by_camera must have at least 2 cameras, got {len(self.camera_node_output_by_camera)}")
        if not all([output.frame_number == self.multi_frame_number for output in
                    self.camera_node_output_by_camera.values()]):
            raise ValueError(
                f"multi_frame_number {self.multi_frame_number} does not match all camera_node_output_by_camera multi_frame_numbers")
        return self

    @property
    def image_points_by_camera(self) -> dict[CameraIdString, list[ImagePoint2D]]:
        image_points_by_camera = {camera_id: [] for camera_id in self.camera_node_output_by_camera.keys()}
        for camera_id, camera_node_output in self.camera_node_output_by_camera.items():
            image_points_by_camera[camera_id].extend(
                list(camera_node_output.charuco_observation.detected_charuco_corners_in_full_array))

        return image_points_by_camera


class SharedViewAccumulator(BaseModel):
    """
    Keeps track of the data feeds from each camera, and keeps track of the frames where each can see the calibration target,
    and counts the number of shared views each camera has with each other camera (i.e. frames where both cameras can see the target)
    """
    camera_ids: list[CameraIdString]
    target_views_by_camera_pair: dict[CameraPair, list[CameraPairTargetView]] = Field(default_factory=dict)

    @property
    def camera_pairs(self) -> list[CameraPair]:
        return list(self.target_views_by_camera_pair.keys())

    @property
    def multi_camera_target_views(self) -> dict[MultiFrameNumber, MultiCameraTargetView]:
        mc_views = {}
        for camera_pair, shared_views in self.target_views_by_camera_pair.items():
            for shared_view in shared_views:
                if not shared_view.multi_frame_number in mc_views:
                    mc_views[shared_view.multi_frame_number] = MultiCameraTargetView(
                        multi_frame_number=shared_view.multi_frame_number,
                        camera_node_output_by_camera=shared_view.camera_node_output_by_camera
                    )
                else:
                    mc_views[shared_view.multi_frame_number].camera_node_output_by_camera.update(
                        shared_view.camera_node_output_by_camera)
        return mc_views

    @classmethod
    def create(cls, camera_ids: list[CameraIdString]):
        camera_pairs = []
        for i, camera_id in enumerate(camera_ids):
            for other_camera_id in camera_ids[i + 1:]:
                camera_pairs.append(CameraPair.from_ids(camera_id, other_camera_id))
        return cls(camera_ids=camera_ids, target_views_by_camera_pair={camera_pair: [] for camera_pair in camera_pairs})

    def receive_camera_node_output(
            self,
            multi_frame_number: int,
            camera_node_output_by_camera: dict[CameraIdString, CameraNodeOutputMessage]
    ):
        for camera_id, camera_node_output in camera_node_output_by_camera.items():
            if not camera_node_output.charuco_observation.charuco_empty:
                for other_camera_id in self.camera_ids:
                    if other_camera_id == camera_id:
                        continue
                    if not camera_node_output_by_camera[other_camera_id].charuco_observation.charuco_empty:
                        camera_pair = CameraPair.from_ids(camera_id, other_camera_id)
                        if camera_pair not in self.target_views_by_camera_pair:
                            raise ValueError(
                                f"camera_pair {camera_pair} not in target_views_by_camera_pair keys {self.target_views_by_camera_pair.keys()}")
                        if any([shared_view.multi_frame_number == multi_frame_number for shared_view in
                                self.target_views_by_camera_pair[camera_pair]]):
                            continue
                        self.target_views_by_camera_pair[camera_pair].append(
                            CameraPairTargetView(
                                multi_frame_number=multi_frame_number,
                                camera_pair=camera_pair,
                                camera_node_output_by_camera={
                                    camera_id: camera_node_output,
                                    other_camera_id: camera_node_output_by_camera[other_camera_id]
                                }
                            )
                        )

    def get_shared_view_count_per_camera(self) -> dict[CameraIdString, int]:
        """
        Get the number of shared views for each camera id, i.e. the number of frames where the camera can see the target and at least one other camera can also see the target
        """
        camera_shared_view_count = {camera_id: 0 for camera_id in self.camera_ids}
        for camera_pair, shared_views in self.target_views_by_camera_pair.items():
            camera_shared_view_count[camera_pair.base_camera_id] += len(shared_views)
            camera_shared_view_count[camera_pair.other_camera_id] += len(shared_views)
        return camera_shared_view_count

    def all_cameras_have_min_shared_views(self, min_shared_views: int = 500) -> bool:
        """
        find the total number of shared views for each camera id within the various camera pairs
        we don't need all possible pairs to have min_shared_views, just that each camera has min_shared_views with at least one other camera
        """
        return all([count >= min_shared_views for count in self.get_shared_view_count_per_camera().values()])

    def get_calibration_observations_if_ready(
            self,
            min_shared_views: int = 10
    ) -> list[CharucoObservations] | None:
        """
        Check if all cameras have the minimum number of shared views.
        If ready, extract and return charuco observations formatted for calibration.
        If not ready, return None.

        Args:
            min_shared_views: Minimum number of shared views required per camera

        Returns:
            List of charuco observations by camera for each frame, or None if not ready
        """
        if not self.all_cameras_have_min_shared_views(min_shared_views=min_shared_views):
            return None

        # Extract observations from multi_camera_target_views
        multi_camera_views = self.multi_camera_target_views

        if len(multi_camera_views) == 0:
            raise ValueError("No multi-camera target views available despite having minimum shared views")

        # Sort by frame number to maintain temporal order
        sorted_frame_numbers = sorted(multi_camera_views.keys())

        # Build list of observations for each frame
        charuco_observations_by_frame: list[CharucoObservations] = []

        for frame_number in sorted_frame_numbers:
            mc_view = multi_camera_views[frame_number]

            # Extract charuco observation for each camera
            observations_for_frame: CharucoObservations = {}
            for camera_id in self.camera_ids:
                if camera_id in mc_view.camera_node_output_by_camera:
                    camera_output = mc_view.camera_node_output_by_camera[camera_id]
                    observations_for_frame[camera_id] = camera_output.charuco_observation
                else:
                    observations_for_frame[camera_id] = None

            charuco_observations_by_frame.append(observations_for_frame)
        logger.info(f"Calibration observations ready with {len(charuco_observations_by_frame)} frames.")
        return charuco_observations_by_frame