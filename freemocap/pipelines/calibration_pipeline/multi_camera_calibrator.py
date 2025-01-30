from pydantic import BaseModel

from freemocap.pipelines.calibration_pipeline.calibration_camera_node_output_data import CalibrationCameraNodeOutputData
from freemocap.pipelines.calibration_pipeline.multi_camera_calibration_estimate import MultiCameraCalibrationEstimate
from freemocap.pipelines.calibration_pipeline.positional_6dof import Positional6DOF
from freemocap.pipelines.calibration_pipeline.shared_view_accumulator import SharedViewAccumulator, TargetViewByCamera
from freemocap.pipelines.calibration_pipeline.single_camera_calibrator import SingleCameraCalibrator

from skellycam import CameraId
class MultiCameraCalibrator(BaseModel):
    calibration_estimate: MultiCameraCalibrationEstimate
    charuco_views_by_cameras: dict[CameraId, list[CalibrationCameraNodeOutputData]]

    @classmethod
    def initialize(cls,
                   shared_charuco_views: list[TargetViewByCamera],
                   calibrate_cameras: bool = True):

        # Calculate the calibration estimate for each camera

        charuco_view_by_camera = {}

        for target_view_by_camera in shared_charuco_views:
            for camera_id, camera_node_output in target_view_by_camera.views_by_camera.items():
                if camera_id not in charuco_view_by_camera:
                    charuco_view_by_camera[camera_id] = []
                charuco_view_by_camera[camera_id].append(camera_node_output)

        # Find the principal camera (usually Camera0, but this finds the lowest indexed camera)
        principal_camera_id = min(key for key in charuco_view_by_camera.keys())
        principal_camera_6dof = Positional6DOF(translation=[0., 0., 0.],
                                               rotation=[0., 0., 0.])

        camera_estimates = {}
        for camera_id, camera_node_outputs in charuco_view_by_camera.items():
            camera_estimates[camera_id] = SingleCameraCalibrator.from_camera_node_outputs(camera_node_outputs=camera_node_outputs,
                                                                                          calibrate_camera=calibrate_cameras).current_estimate

        return cls(calibration_estimate=MultiCameraCalibrationEstimate(principal_camera_id=principal_camera_id,
                                                                       principal_camera_6dof=principal_camera_6dof,
                                                                       camera_estimates=camera_estimates),
                     charuco_views_by_cameras=charuco_view_by_camera)
