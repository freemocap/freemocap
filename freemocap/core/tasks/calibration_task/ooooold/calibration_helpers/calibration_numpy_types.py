import numpy as np
from numpydantic import NDArray, Shape

ReprojectionError = float

ImagePoint2D = NDArray[Shape["2 pixelx_pixely"], np.float64]
ImagePoints2D = NDArray[Shape["* n_points, 2 pixelx_pixely"], np.float64]
ImagePoints2DByCamera = NDArray[Shape[
    "* n_cams, * n_points, 2 pixelx_pixely"], np.float64]  # e.g. Image coordinates of a point in 3d space projected onto each camera

ObjectPoint3D = NDArray[Shape["3 xyz"], np.float64]
ObjectPoints3D = NDArray[Shape["* n_points, 3 xyz"], np.float64]
PointIds = NDArray[Shape["* n_points"], np.int64]

RotationVectorArray = NDArray[Shape["3"], np.float64]
RotationMatrixArray = NDArray[Shape["3 rows, 3 columns"], np.float64]
QuaternionArray = NDArray[Shape["4 xyzw"], np.float64]
TranslationVectorArray = NDArray[Shape["3"], np.float64]
RotationVectorsByCamera = NDArray[Shape["* n_cams, 3"], np.float64]
TranslationVectorsByCamera = NDArray[Shape["* n_cams, 3"], np.float64]

CameraMatrixArray = NDArray[Shape["3 rows, 3 columns"], np.float64]
CameraExtrinsicsMatrix = NDArray[Shape["3 rows, 4 columns"], np.float64]
CameraMatrixByCamera = NDArray[Shape["* n_cams, 3 rows, 3 columns"], np.float64]
CameraExtrinsicsMatrixByCamera = NDArray[Shape["* n_cams, 4 rows, 4 columns"], np.float64]
TransformationMatrixArray = NDArray[Shape[
    "4 rows, 4 columns"], np.float64]  # 4x4 matrix that transforms points from the camera coordinate system to the world coordinate system. 3x3 in the upper left is the rotation matrix, and the rightmost column is the translation vector. The bottom row is [0, 0, 0, 1] (where the 1 is the homogeneous coordinate, which makes the matrix invertible and provides the scale factor for the translation vector to put it in spatial coordinates

CameraDistortionCoefficientsArray = NDArray[
    Shape["4-14 k1_k2_p1_p2_k3_k4_k5_k6"], np.float64]  # Can be 4,5,8,12, or 14 elements

ExtrinsicsParameters = NDArray[Shape["6 translation_rotation"], np.float64]  # 3 for rotation, 3 for translation
IntrinsicsParameters = NDArray[
    Shape["*, ..."], np.float64]  # focal length, variable number of distortion coefficients (2, 4, 5, 8, 12, or 14)

ExtrinsicsParametersByCamera = NDArray[Shape["* n_cams, 6 translation_rotation"], np.float64]
IntrinsicsParametersByCamera = NDArray[Shape["* n_cams, * focal_length_distortion"], np.float64]

JacobianMatrixArray = NDArray[Shape["* m_n_error_function_returns, * n_parameters"], np.float64]

SparseBundleOptimizerGuess1D = NDArray[Shape["* n_parameters"], np.float64]
