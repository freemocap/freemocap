from pydantic import BaseModel
from pydantic import Field
from skellycam import CameraId

from freemocap.core.tasks.calibration_task.calibration_helpers.calibration_numpy_types import \
    TransformationMatrixArray, CameraMatrixArray, CameraDistortionCoefficientsArray
from freemocap.core.tasks.calibration_task.calibration_helpers.positional_6dof import Positional6DoF


class SingleCameraCalibrationEstimate(BaseModel):
    camera_id: CameraId

    camera_matrix: CameraMatrixArray
    distortion_coefficients: CameraDistortionCoefficientsArray

    positional_6dof: Positional6DoF = Field(default_factory=Positional6DoF)


    @property
    def focal_length(self):
        fx = self.camera_matrix[0, 0]
        fy = self.camera_matrix[1, 1]
        return (fx + fy) / 2.0

    @focal_length.setter
    def focal_length(self, fx: float, fy: float = None):
        if fy is None:
            fy = fx
        self.camera_matrix[0, 0] = fx
        self.camera_matrix[1, 1] = fy

    def extrinsic_matrix(self) -> TransformationMatrixArray:
        return self.positional_6dof.transformation_matrix

