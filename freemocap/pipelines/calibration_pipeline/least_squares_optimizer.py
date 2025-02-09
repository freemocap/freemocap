import numpy as np
from pydantic import BaseModel
from pydantic import model_validator
from scipy import optimize
from scipy.sparse import dok_matrix
from skellycam import CameraId
from typing_extensions import Self

from freemocap.pipelines.calibration_pipeline.calibration_numpy_types import \
    ImagePoints2D, ImagePoint2D, CameraExtrinsicsMatrix
from freemocap.pipelines.calibration_pipeline.camera_math_models import TransformationMatrix
from freemocap.pipelines.calibration_pipeline.shared_view_accumulator import MultiCameraTargetView, MultiFrameNumber
from freemocap.pipelines.calibration_pipeline.single_camera_calibrator import CameraIntrinsicsEstimate
from freemocap.pipelines.calibration_pipeline.triangulate_points import undistort_points, \
    calculate_reprojection_error, triangulate_point


class SparseBundleOptimizer(BaseModel):
    principal_camera_id: CameraId
    initial_guess: dict[CameraId, CameraExtrinsicsMatrix]
    image_points_by_camera: dict[CameraId, list[ImagePoint2D]]
    camera_intrinsics: dict[CameraId, CameraIntrinsicsEstimate]
    image_sizes: dict[CameraId, tuple[int, int]]

    @classmethod
    def create(cls,
               principal_camera_id: CameraId,
               camera_extrinsics_by_camera_id: dict[CameraId, CameraExtrinsicsMatrix],
               multi_camera_target_views: dict[MultiFrameNumber, MultiCameraTargetView],
               camera_intrinsics: dict[CameraId, CameraIntrinsicsEstimate],
               image_sizes: dict[CameraId, tuple[int, int]]
               ) -> "SparseBundleOptimizer":
        image_points_by_camera: dict[CameraId, list[ImagePoint2D]] = {camera_id: [] for camera_id in
                                                                      camera_intrinsics.keys()}
        for frame_number, target_view in multi_camera_target_views.items():
            for camera_id, image_points in target_view.image_points_by_camera.items():
                image_points_by_camera[camera_id].extend(image_points)
        return cls(
            image_points_by_camera=image_points_by_camera,
            camera_intrinsics=camera_intrinsics,
            initial_guess=camera_extrinsics_by_camera_id,
            principal_camera_id=principal_camera_id,
            image_sizes=image_sizes
        )

    @model_validator(mode='after')
    def validate(self) -> Self:
        # make sure the principal camera is in all the keys, along with at least one other camera
        if self.principal_camera_id not in self.initial_guess or len(self.initial_guess) < 2:
            raise ValueError("Principal camera must be in the initial guess and there must be at least two cameras")
        camera_ids = self.initial_guess.keys()
        if not all([camera_ids == self.image_points_by_camera.keys(),
                    camera_ids == self.camera_intrinsics.keys(),
                    camera_ids == self.image_points_by_camera.keys(),
                    camera_ids == self.image_sizes.keys()]):
            raise ValueError("All camera ids must be the same across all inputs")
        for camera_id, image_points in self.image_points_by_camera.items():
            if len(image_points) < 2:
                raise ValueError(f"Camera {camera_id} must have at least two image points")
            if len(image_points) != self.number_of_points:
                raise ValueError(
                    f"Camera {camera_id} must have the same number of image points as the principal camera")
        return self

    @property
    def number_of_optimization_parameters(self) -> int:
        return len(self.starting_guess_vector)

    @property
    def number_of_parameters_per_camera(self) -> int:
        return self.initial_guess[self.principal_camera_id].size

    @property
    def number_of_points(self) -> int:
        return len(self.image_points_by_camera[self.principal_camera_id])

    @property
    def starting_guess_vector(self) -> list[float]:
        starting_guess = []
        for camera_id, extrinsics in self.initial_guess.items():
            starting_guess.extend(extrinsics.flatten().tolist())
        return starting_guess

    def optimize(self) -> optimize.OptimizeResult:

        # Set up optimization options
        return optimize.least_squares(
            fun=self.error_function,
            x0=self.starting_guess_vector,
            # jac_sparsity=self.get_jacobian_sparse_matrix(),
            jac="3-point",  # TODO- could prob use `callable` and calc the jacobian dynamically
            f_scale=50.0,  # TODO - Not sure where this number comes from
            x_scale="jac",
            loss="soft_l1",#"linear",  # TODO - try `soft_l1` or `cauchy`
            # ftol=1e-4,
            method="trf",
            verbose=2,
            bounds=(-np.inf, np.inf),  # TODO - set bounds to reasonable values
            max_nfev=1000,
            kwargs=dict(camera_intrinsics=self.camera_intrinsics,
                        image_points_by_camera=self.image_points_by_camera,
                        principal_camera_id=self.principal_camera_id,
                        image_sizes=self.image_sizes),

        )

    def error_function(self,
                       current_guess: list[float],
                       camera_intrinsics: dict[CameraId, CameraIntrinsicsEstimate],
                       image_points_by_camera: dict[CameraId, ImagePoints2D],
                       principal_camera_id: CameraId,
                       image_sizes: dict[CameraId, tuple[int, int]]
                       ) -> list[float]:

        # reform 'current_guess' into camera extrinsics matricies
        camera_ids = list(self.camera_intrinsics.keys())
        camera_transforms: dict[CameraId, TransformationMatrix] = {}
        camera_extrinsics: dict[CameraId, CameraExtrinsicsMatrix] = {}
        undistored_image_points: dict[CameraId, ImagePoints2D] = {}
        for camera_index, camera_id in enumerate(camera_ids):
            # split the 1d vector by camera based on `self.number_of_parameters_per_camera`
            starting_index = camera_index * self.number_of_parameters_per_camera
            ending_index = (camera_index + 1) * self.number_of_parameters_per_camera
            camera_transforms[camera_id] = TransformationMatrix.from_extrinsics(
                extrinsics_matrix=np.array(current_guess[starting_index:ending_index]).reshape(3, 4),
                reference_frame=f"camera-{principal_camera_id}")
            camera_extrinsics[camera_id] = camera_transforms[camera_id].extrinsics_matrix
            # undistort the image points for each camera using the camera intrinsics
            undistored_image_points[camera_id] = undistort_points(
                points2d=np.asarray(image_points_by_camera[camera_id]),
                camera_intrinsics=camera_intrinsics[camera_id])
            # re-scale from normalized image coordinates to pixel coordinates
            # undistored_image_points[camera_id][:, 0] *= image_sizes[camera_id][0]
            # undistored_image_points[camera_id][:, 1] *= image_sizes[camera_id][1]
        # triangulate 3D points from 2D points using camera extrinsics and intrinsics (provided as kwargs)
        points3d = []
        for point_index in range(self.number_of_points):
            # triangulate the 3D point from the 2D points
            image_point_by_camera = {camera_id: undistored_image_points[camera_id][point_index]
                                     for camera_id in camera_ids}
            points3d.append(triangulate_point(image_point_by_camera=image_point_by_camera,
                                              camera_extrinsics=camera_extrinsics))

        # calculate reprojection error for each point
        reprojection_error_by_point, _ = calculate_reprojection_error(object_points=np.asarray(points3d),
                                                                      image_points_by_camera=undistored_image_points,
                                                                      camera_transforms=camera_transforms,
                                                                      camera_intrinsics=camera_intrinsics,
                                                                      image_sizes=image_sizes)

        return np.mean(reprojection_error_by_point)

    def get_jacobian_sparse_matrix(self) -> dok_matrix:
        jacobian_matrix = np.ones((self.number_of_points, self.number_of_optimization_parameters))

        # TODO - Implement the logic to populate the jacobian_matrix based on the current guess and image points
        # basically for each row (point2d) on the jacobian matrix, we need to populate the columns (parameters) that are affected by that point
        # so the parameters for the camea that can't see each point should be zero

        for point_index in range(self.number_of_points):
            row_values = []
            num_cams_that_can_see_point = 0
            for camera_id, image_points in self.image_points_by_camera.items():
                if np.isnan(image_points[point_index][0]) or np.isnan(image_points[point_index][1]):
                    row_values.append(np.zeros(self.number_of_parameters_per_camera))
                else:
                    num_cams_that_can_see_point += 1
                    row_values.append(np.ones(self.number_of_parameters_per_camera))
            if num_cams_that_can_see_point < 2:
                row_values = [np.zeros(self.number_of_parameters_per_camera) for _ in range(len(row_values))]
            jacobian_matrix[point_index] = np.concatenate(row_values)

        return dok_matrix(jacobian_matrix).tocsr()
