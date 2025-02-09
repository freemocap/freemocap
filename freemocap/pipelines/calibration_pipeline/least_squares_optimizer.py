from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pydantic import BaseModel
from scipy import optimize
from scipy.sparse import dok_matrix
from skellycam import CameraId

from freemocap.pipelines.calibration_pipeline.calibration_numpy_types import \
    JacobianMatrixArray
from freemocap.pipelines.calibration_pipeline.shared_view_accumulator import MultiCameraTargetView, MultiFrameNumber
from freemocap.pipelines.calibration_pipeline.single_camera_calibrator import CameraIntrinsicsEstimate, \
    TransformationMatrix

if TYPE_CHECKING:
    pass


class LeastSquaresOptimizerStartingGuess(BaseModel):
    pass

    @abstractmethod
    def to_list(self) -> list[float]:
        pass


class LeastSquaresOptimizerABC(BaseModel, ABC):
    initial_guess: object
    loss: str = "linear"
    maximum_number_function_evals: int = 1000
    threshold: float = 50.0
    function_tolerance: float = 1e-4
    jacobian_sparsity_matrix: JacobianMatrixArray | None = None

    @classmethod
    @abstractmethod
    def create(cls, **kwargs) -> "LeastSquaresOptimizerABC":
        pass

    @property
    def starting_guess(self) -> list[float]:
        return self.initial_guess_model

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
            kwargs=self.error_function_input.model_dump()
        )


class SparseBundleOptimizer(LeastSquaresOptimizerABC):
    principal_camera_id: CameraId
    initial_guess: dict[CameraId, TransformationMatrix]
    multi_camera_target_views: dict[MultiFrameNumber, MultiCameraTargetView]
    camera_intrinsics: dict[CameraId, CameraIntrinsicsEstimate]

    @classmethod
    def create(cls,
               principal_camera_id: CameraId,
               camera_extrinsic_transforms_by_camera_id: dict[CameraId, TransformationMatrix],
               multi_camera_target_views: dict[MultiFrameNumber, MultiCameraTargetView],
               camera_intrinsics: dict[CameraId, CameraIntrinsicsEstimate]
               ) -> "SparseBundleOptimizer":
        return cls(
            multi_camera_target_views=multi_camera_target_views,
            camera_intrinsics=camera_intrinsics,
            initial_guess=camera_extrinsic_transforms_by_camera_id,
            principal_camera_id=principal_camera_id
        )

    def error_function(self,
                       current_guess: list[float],
                       **kwargs
                       ) -> float:
        try:
            camera_matrices =kwargs['camera_matrices']
            multi_camera_target_views = kwargs['multi_camera_target_views']
            principal_camera_id = kwargs['principal_camera_id']
        except KeyError:
            raise ValueError("Missing required keyword arguments")
        # reform 'current_guess' into camera extrinsics matricies

        # triangulate 3D points from 2D points using camera extrinsics and intrinsics (provided as kwargs)

        # calculate reprojection error
        error = 0.0
        return error

    def get_jacobian_sparse_matrix(self, current_guess: list[float], **kwargs) -> dok_matrix:
        pass
