from abc import ABC, abstractmethod

import numpy as np
from pydantic import BaseModel
from scipy import optimize
from scipy.sparse import dok_matrix, csr_matrix
from skellycam import CameraId

from freemocap.pipelines.calibration_pipeline.multi_camera_calibration.calibration_numpy_types import \
    CameraDistortionCoefficients, CameraMatrixByCamera, PixelPoints2DByCamera, CameraMatrix, JacobianSparsityMatrix

DataPointName = str
DataPointId = int
DataPointValue = float | int
DataMaxValue = DataMinValue = float | int | None


class Datum(BaseModel):
    """
    A solitary data point

    id should be unique within the dataset,
    name is descriptive for humans and should specify where this datum lives within the dataset,
    datum is a  scalar representing the value of this data point
    max and min are the maximum and minimum values this datum can take (if applicable)
    """
    name: DataPointName
    id: DataPointId
    value: DataPointValue
    max: DataMaxValue = None
    min: DataMinValue = None


class RelevantDataABC(BaseModel, ABC):
    data: dict[DataPointName, Datum]

    @abstractmethod
    def as_1d_vector(self) -> list[DataPointValue]:
        ids = []
        for datum in self.data.values():
            if datum.id in ids:
                raise ValueError(f"Duplicate id {datum.id} found in data")
            ids.append(datum.id)

        return [datum.value for datum in self.data.values()]


class OptimizerInputDataABC(BaseModel, ABC):
    relevant_data: RelevantDataABC
    initial_guess: list[float]
    jacobian_sparsity_matrix: JacobianSparsityMatrix | None = None

    @abstractmethod
    def calculate_jacobian_sparsity_matrix(self):
        pass

    @abstractmethod
    def is_datapoint_relevant_to_this_part_of_the_initial_guess(self, data_point: Datum) -> bool:
        pass


class LeastSquaresOptimizerABC(BaseModel, ABC):
    input_data: OptimizerInputDataABC
    loss: str = "linear"
    maximum_number_function_evals: int = 1000
    threshold: float = 50.0
    function_tolerance: float = 1e-4
    jacobian_sparsity_matrix: JacobianSparsityMatrix | None = None

    @classmethod
    @abstractmethod
    def create(cls, input_data: OptimizerInputDataABC) -> "LeastSquaresOptimizerABC":
        pass

    @abstractmethod
    def error_function(self, current_guess: list[float], **kwargs) -> float:
        pass

    @abstractmethod
    def get_jacobian_sparse_matrix(self, current_guess: list[float], **kwargs) -> dok_matrix:
        pass

    def optimize(self) -> optimize.OptimizeResult:
        # Set up optimization options
        return optimize.least_squares(
            fun=self.error_function,
            x0=self.starting_guess,
            jac_sparsity=self.get_jacobian_sparse_matrix(self.starting_guess),
            f_scale=self.threshold,
            x_scale="jac",
            loss=self.loss,
            ftol=self.function_tolerance,
            method="trf",
            verbose=2,
            max_nfev=self.maximum_number_function_evals,
            args=(),
        )


class SparseBundleAdjustmentOptimizerInputData(OptimizerInputDataABC):
    camera_matricies: CameraMatrixByCamera
    image_points_2d_by_camera: PixelPoints2DByCamera
    camera_distortion_coefficients: CameraDistortionCoefficients | None = None
    jacobian_sparsity_matrix: JacobianSparsityMatrix | None = None

    def calculate_jacobian_sparsity_matrix(self):
        pass

    def is_datapoint_relevant_to_this_part_of_the_initial_guess(self, data_point: Datum) -> bool:
        pass

    @classmethod
    def create(cls,
               camera_matricies: dict[CameraId, CameraMatrix],
               input_2d_observations_in_image_coordinates_by_camera: list[PixelPoints2DByCamera],
               camera_distortion_coefficients: CameraDistortionCoefficients | None = None,
               ) -> "SparseBundleAdjustmentOptimizerInputData":
        return cls(camera_matricies=np.hstack([camera_matrix for camera_matrix in camera_matricies.values()]),
                   image_points_2d_by_camera=input_2d_observations_in_image_coordinates_by_camera,
                   camera_distortion_coefficients=camera_distortion_coefficients)


class SparseBundleAdjustmentOptimizer(LeastSquaresOptimizerABC):
    input_data: SparseBundleAdjustmentOptimizerInputData

    @classmethod
    def create(cls, input_data: SparseBundleAdjustmentOptimizerInputData) -> "SparseBundleAdjustmentOptimizer":
        return cls(input_data=input_data,
                   jacobian_sparsity_matrix=input_data.jacobian_sparsity_matrix)

    @property
    def starting_guess(self) -> list[float]:
        return self.input_data.camera_matrices.flatten().tolist()

    def error_function(self, current_guess: list[float], **kwargs) -> float:
        if not all(k in kwargs for k in ("camera_matrices", "camera_distortion_coefficients")):
            raise ValueError("Missing required kwargs 'camera_matrices' and/OR 'camera_distortion_coefficients'")

        # reform 'current_guess' into camera extrinsics matricies

        # triangulate 3D points from 2D points using camera extrinsics and intrinsics (provided as kwargs)

        # calculate reprojection error
        error = 0.0
        return error

    def get_jacobian_sparse_matrix(self, current_guess: list[float], **kwargs) -> dok_matrix:
        pass
