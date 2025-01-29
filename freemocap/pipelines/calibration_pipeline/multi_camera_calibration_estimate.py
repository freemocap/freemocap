from pydantic import BaseModel
from skellycam import CameraId

from freemocap.pipelines.calibration_pipeline.positional_6dof import Positional6DOF
from freemocap.pipelines.calibration_pipeline.single_camera_calibration_estimate import SingleCameraCalibrationEstimate


class MultiCameraCalibrationEstimate(BaseModel):
    principal_camera_id: CameraId
    principal_camera_6dof: Positional6DOF
    camera_estimates: dict[CameraId, SingleCameraCalibrationEstimate]
