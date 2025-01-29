import numpy as np
from numpydantic import NDArray, Shape
from pydantic import BaseModel


class SingleCameraCalibrationEstimate(BaseModel):
    camera_matrix: NDArray[Shape["3, 3"], np.float64]
    distortion_coefficients: NDArray[Shape["5"], np.float64]
    mean_reprojection_errors: list[float]
    camera_calibration_residuals: list[float]
    reprojection_error_by_view: list[float]
