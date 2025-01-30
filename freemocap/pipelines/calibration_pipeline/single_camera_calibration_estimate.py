import numpy as np
from numpydantic import NDArray, Shape
from pydantic import BaseModel

from pydantic import Field

from freemocap.pipelines.calibration_pipeline.multi_camera_calibration.calibration_numpy_types import \
    TransformationMatrix
from freemocap.pipelines.calibration_pipeline.positional_6dof import Positional6DoF
from skellycam import CameraId

class SingleCameraCalibrationEstimate(BaseModel):
    camera_id: CameraId

    camera_matrix: NDArray[Shape["3, 3"], np.float64]
    distortion_coefficients: NDArray[Shape["5"], np.float64]

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

    def extrinsic_matrix(self) -> TransformationMatrix:
        return self.positional_6dof.transformation_matrix