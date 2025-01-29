from typing import Dict

from pydantic import BaseModel
from skellycam import CameraId

from freemocap.pipelines.calibration_pipeline.calibration_camera_node_output_data import CalibrationCameraNodeOutputData


class SharedViewAccumulator(BaseModel):
    """
    Keeps track of the data feeds from each camera, and keeps track of the frames where each can see the calibration target,
    and counts the number of shared views each camera has with each other camera (i.e. frames where both cameras can see the target)
    """
    camera_ids: list[CameraId]
    camera_node_outputs_by_frame: dict[int, Dict[CameraId, CalibrationCameraNodeOutputData]]

    @classmethod
    def create(cls, camera_ids: list[CameraId]):
        return cls(camera_ids=camera_ids, camera_node_outputs_by_frame={})

    @property
    def shared_views_per_camera_by_camera(self) -> dict[CameraId, dict[CameraId, int]]:
        shared_views_by_camera = {
            camera_id: {other_camera_id: 0 for other_camera_id in self.camera_ids if other_camera_id != camera_id}
            for camera_id in self.camera_ids}
        for frame_number, camera_view_records in self.camera_node_outputs_by_frame.items():
            for camera_id, camera_view_record in camera_view_records.items():
                for other_camera_view_record in camera_view_records.values():
                    if other_camera_view_record.camera_id == camera_id:
                        continue
                        # shared_views_by_camera[camera_id][other_camera_view_record.camera_id] += 1

                    if camera_view_records[camera_id].can_see_target and other_camera_view_record.can_see_target:
                        shared_views_by_camera[camera_id][other_camera_view_record.camera_id] += 1
        return shared_views_by_camera

    @property
    def shared_views_total_per_camera(self) -> dict[CameraId, int]:
        return {camera_id: sum(shared_views.values()) for camera_id, shared_views in
                self.shared_views_per_camera_by_camera.items()}

    def all_cameras_have_min_shared_views(self, min_shared_views: int) -> bool:
        return all(shared_views >= min_shared_views for shared_views in self.shared_views_total_per_camera.values())

    def receive_camera_node_output(self, multi_frame_number: int,
                                   camera_node_output: dict[CameraId, CalibrationCameraNodeOutputData]):
        self.camera_node_outputs_by_frame[multi_frame_number] = camera_node_output

    def shared_camera_views(self) -> dict[CameraId, dict[int, CalibrationCameraNodeOutputData]]:
        shared_views = {camera_id: {other_camera_id: camera_node_output for other_camera_id, camera_node_output in
                                    camera_view_records.items() if camera_node_output.can_see_target}
                        for camera_id, camera_view_records in self.camera_node_outputs_by_frame.items()}
        return shared_views