from pydantic import BaseModel
from skellycam import CameraId

from freemocap.pipelines.calibration_pipeline.calibration_camera_node_output_data import CalibrationCameraNodeOutputData
from freemocap.pipelines.calibration_pipeline.multi_camera_calibration_estimate import MultiCameraCalibrationEstimate
from freemocap.pipelines.calibration_pipeline.positional_6dof import Positional6DOF
from freemocap.pipelines.calibration_pipeline.single_camera_calibrator import SingleCameraCalibrator

FrameNumber = int


class MultiCameraCalibrator(BaseModel):
    calibration_estimate: MultiCameraCalibrationEstimate

    @classmethod
    def initialize(cls,
                   shared_charuco_views: dict[FrameNumber, dict[CameraId, CalibrationCameraNodeOutputData]],
                   calibrate_cameras: bool = True):
        # Find the principal camera
        principal_camera_id = min(key for key in shared_charuco_views.keys())
        principal_camera_6dof = Positional6DOF(translation=[0., 0., 0.],
                                               rotation=[0., 0., 0.])

        # Calculate the calibration estimate for each camera
        camera_node_outputs_by_camera = {camera_id: [] for camera_id in shared_charuco_views[0].keys()}
        for frame_number, camera_node_outputs in shared_charuco_views.items():
            for camera_id in camera_node_outputs.keys():
                camera_node_outputs_by_camera[camera_id].append(camera_node_outputs[camera_id])

        camera_estimates = {}
        for camera_id, camera_node_outputs in camera_node_outputs_by_camera.items():
            camera_estimates[camera_id] = SingleCameraCalibrator.from_camera_node_outputs(camera_node_outputs=camera_node_outputs,
                                                                                          calibrate_camera=calibrate_cameras).current_estimate

        return cls(calibration_estimate=MultiCameraCalibrationEstimate(principal_camera_id=principal_camera_id,
                                                                       principal_camera_6dof=principal_camera_6dof,
                                                                       camera_estimates=camera_estimates))
