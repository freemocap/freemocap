# Most of this was copied (with permission) from the original `aniposelib` package (https://github.com/lambdaloop/aniposelib), and we're adapting it to our needs here. M
# ore info on Anipoise: https://anipose.readthedocs.io/en/latest/

import logging
import multiprocessing
from typing import Any

import numpy as np
from freemocap.core_processes.capture_volume_calibration.anipose_camera_calibration.anipose_stuff.anipose_camera import \
    AniposeCamera
from freemocap.core_processes.capture_volume_calibration.anipose_camera_calibration.anipose_stuff.anipose_functions import \
    get_error_dict, subset_extra, resample_points_based_on_shared_views, remap_ids, \
    transform_points, make_M, get_rtvec, calculate_error_bounds
from freemocap.core_processes.capture_volume_calibration.anipose_camera_calibration.anipose_stuff.anipose_triangulate_simple import \
    anipose_triangulate_simple
from numba import jit
from scipy import optimize
from scipy.linalg import inv as inverse
from scipy.sparse import dok_matrix
from tqdm import trange

logger = logging.getLogger(__name__)


class AniposeCameraGroup:
    def __init__(self, cameras: list[AniposeCamera], metadata: dict[str, Any]):
        self.cameras = cameras
        self.metadata = metadata

    def project_3d_to_2d(self, points3d: np.ndarray):
        """Given an Nx3 array of points, this returns an CxNx2 array of 2D points,
        where C is the number of cameras"""
        points3d = points3d.reshape(-1, 1, 3)
        n_points = points3d.shape[0]
        n_cams = len(self.cameras)

        projected_points2d = np.empty((n_cams, n_points, 2), dtype="float64")
        for camera_number, camera in enumerate(self.cameras):
            projected_points2d[camera_number] = camera.project_3d_to_2d(points3d).reshape(n_points, 2)

        # check shape
        assert projected_points2d.shape == (n_cams, n_points,
                                            2), f"Invalid projected_points2d shape, should be {n_cams, n_points, 2}, but shape is {projected_points2d.shape}"

        return projected_points2d

    def triangulate(self, points2d, undistort=True, progress=False, kill_event: multiprocessing.Event = None):
        """Given an CxNx2 array, this returns an Nx3 array of points,
        where N is the number of points and C is the number of cameras"""

        assert points2d.shape[0] == len(
            self.cameras
        ), "Invalid points shape, first dim should be equal to" " number of cameras ({}), but shape is {}".format(
            len(self.cameras), points2d.shape
        )

        one_point = False
        if len(points2d.shape) == 2:
            points2d = points2d.reshape(-1, 1, 2)
            one_point = True

        if undistort:
            new_points = np.empty(points2d.shape)
            for camera_number, camera in enumerate(self.cameras):
                # must copy in order to satisfy opencv underneath
                sub = np.copy(points2d[camera_number])
                new_points[camera_number] = camera.undistort_points(sub)
            points2d = new_points

        n_cams, n_points, _ = points2d.shape

        triangulated_points3d = np.empty((n_points, 3))
        triangulated_points3d[:] = np.nan

        camera_matricies = np.array([camera.get_extrinsics_mat() for camera in self.cameras])

        if progress:
            points_iterator = trange(n_points, ncols=70)
        else:
            points_iterator = range(n_points)

        for point_index in points_iterator:
            point_xy = points2d[:, point_index, :]
            point_xy_no_nans = ~np.isnan(point_xy[:, 0])
            if np.sum(point_xy_no_nans) >= 2:
                triangulated_points3d[point_index] = anipose_triangulate_simple(point_xy[point_xy_no_nans],
                                                                                camera_matricies[point_xy_no_nans])

            if kill_event is not None and kill_event.is_set():
                return None

        if one_point:
            triangulated_points3d = triangulated_points3d[0]

        return triangulated_points3d

    @jit(parallel=True, forceobj=True)
    def calculate_reprojection_error(self,
                                     points_3d: np.ndarray,
                                     points_2d: np.ndarray,
                                     mean=False):
        """Given an Nx3 array of 3D points and an CxNx2 array of 2D points,
        where N is the number of points and C is the number of cameras,
        this returns an CxNx2 array of errors.
        Optionally mean=True, this averages the errors and returns array of length N of errors"""
        if not points_3d.shape[0] == points_2d.shape[1]:
            raise ValueError(
                f"Invalid points shape, first dim of 3D points should be equal to"
                f" number of points in 2D points ({points_2d.shape[1]}), but shape is {points_3d.shape}"
            )
        if not points_2d.shape[0] == len(self.cameras):
            raise ValueError(
                f"Invalid points shape, first dim of 2D points should be equal to"
                f" number of cameras ({len(self.cameras)}), but shape is {points_2d.shape}"
            )
        if not points_3d.shape[1] == 3:
            raise ValueError(f"Invalid points shape, second dim of 3D points should be 3, but shape is {points_3d.shape}")

        if not points_2d.shape[2] == 2:
            raise ValueError(f"Invalid points shape, third dim of 2D points should be 2, but shape is {points_2d.shape}")

        one_point = False
        if len(points_3d.shape) == 1 and len(points_2d.shape) == 2:
            points_3d = points_3d.reshape(1, 3)
            points_2d = points_2d.reshape(-1, 1, 2)
            one_point = True

        n_cams, n_points, _ = points_2d.shape
        if not  points_3d.shape == (n_points,            3,        ):
            raise ValueError("shapes of 2D and 3D points are not consistent: " "2D={}, 3D={}".format(points_2d.shape, points_3d.shape))

        errors = np.empty((n_cams, n_points, 2))

        for camera_number, cam in enumerate(self.cameras):
            errors[camera_number] = cam.single_camera_reprojection_error(points_3d, points_2d[camera_number])

        if mean:
            errors_norm = np.linalg.norm(errors, axis=2)
            good = ~np.isnan(errors_norm)
            errors_norm[~good] = 0
            denom = np.sum(good, axis=0).astype("float64")
            denom[denom < 1.5] = np.nan
            errors = np.sum(errors_norm, axis=0) / denom

        if one_point:
            if mean:
                errors = float(errors[0])
            else:
                errors = errors.reshape(-1, 2)

        return errors

    def run_iterative_bundle_adjustment(
            self,
            points2d: np.ndarray,
            extra_data: dict[str, Any] | None = None,
            max_iterations: int = 10,
            starting_error_threshold: float = 15.0,
            ending_error_threshold: float = 1.0,
            max_number_function_evals: int = 200,
            function_tolerance: float = 1e-4,
            number_of_samples_per_iteration: int = 100,
            number_of_samples_full: int = 1000,
            error_threshold: float = 0.3,
            verbose: bool = False,
    ) -> float:
        """Performs iterative bundle adjustment to refine camera parameters.

        Args:
            points2d (np.ndarray): A CxNx2 array of 2D points, where C is the number of cameras
                and N is the number of points.
            extra_data (Optional[Dict[str, Any]]): Optional dictionary for additional data associated
                with the points.
            max_iterations (int): Maximum number of iterations for the adjustment.
            starting_error_threshold (float): Initial value for the error threshold.
            ending_error_threshold (float): Final value for the error threshold.
            max_number_function_evals (int): Maximum number of function evaluations in bundle adjustment.
            function_tolerance (float): Tolerance for function convergence in bundle adjustment.
            number_of_samples_per_iteration (int): Number of points to sample per iteration.
            number_of_samples_full (int): Number of points for full sampling.
            error_threshold (float): Error threshold for early stopping.
            verbose (bool): If True, prints detailed logs during execution.

        Returns:
            float: Final mean reprojection error after adjustments.
        """
        # Validate input shapes
        assert points2d.ndim == 3 and points2d.shape[2] == 2, "points2d must be a CxNx2 array"
        assert points2d.shape[0] == len(self.cameras), (
            f"Invalid points shape, expected first dimension to be equal to "
            f"number of cameras ({len(self.cameras)}), but got shape {points2d.shape}"
        )

        # Initialize
        error_list = []
        original_points2d = points2d
        original_extra_data = extra_data

        if verbose:
            original_error = self.get_mean_reprojection_error(points2d, median=True)
            logger.info(
                f"Starting iterative bundle adjustment...\n Number of cameras: {len(self.cameras)}\nNumber of points: {points2d.shape[1]}\nOriginal error: {original_error:.2f}")

        # Resample initial set of points to prioritize shared views
        points2d, extra_data = resample_points_based_on_shared_views(
            original_points2d,
            original_extra_data,
            number_of_samples_to_return=number_of_samples_full
        )
        initial_error = self.get_mean_reprojection_error(points2d, median=True)
        if verbose:
            logger.debug("Initial error after resampling: ", initial_error)

        # Calculate dynamic error thresholds for each iteration
        error_thresholds = np.exp(
            np.linspace(np.log(starting_error_threshold), np.log(ending_error_threshold), num=max_iterations))
        if verbose:
            logger.debug(f"Error thresholds we will use for each bundle adjustment iteration: {error_thresholds}")

        # Iterative bundle adjustment
        dynamic_error_threshold = starting_error_threshold
        for iteration in range(max_iterations):
            resampled_points2d, resampled_extra_data = resample_points_based_on_shared_views(
                original_points2d, original_extra_data, number_of_samples_to_return=number_of_samples_full
            )

            # Triangulate 3D points from resampled 2D points
            triangulated_points3d = self.triangulate(resampled_points2d)

            # Calculate reprojection errors
            errors_full = self.calculate_reprojection_error(
                triangulated_points3d, resampled_points2d, mean=False
            )
            normalized_errors = self.calculate_reprojection_error(
                triangulated_points3d, resampled_points2d, mean=True
            )

            # Compute error statistics
            error_dict = get_error_dict(errors_full)
            max_error, min_error = calculate_error_bounds(error_dict)
            dynamic_error_threshold = max(min(max_error, error_thresholds[iteration]), min_error)

            # Determine good points based on current threshold
            good_points_mask = normalized_errors < dynamic_error_threshold
            filtered_extra_data = subset_extra(resampled_extra_data, good_points_mask)

            # Update error list and check for convergence
            current_error = np.median(normalized_errors)
            error_list.append(current_error)
            if current_error < error_threshold:
                if verbose:
                    logger.debug(f"Converged after {iteration + 1} iterations")
                break

            if verbose:
                logger.debug(f"Bundle Adjust Iteration {iteration + 1} -"
                             f"\n\tError: {current_error:.2f}, "
                             f"\n\tThreshold: {dynamic_error_threshold:.1f}, "
                             f"\n\tProportion of points that meet this threshold: {np.mean(good_points_mask):.3f}")
                logger.debug("Error scores from prior iterations", error_list)

            # Perform bundle adjustment
            self.bundle_adjust_points2d(
                resampled_points2d[:, good_points_mask],
                filtered_extra_data,
                loss="linear",
                function_tolerance=function_tolerance,
                maximum_number_function_evals=max_number_function_evals,
                verbose=verbose,
            )

        # Final adjustments and error calculation
        final_resampled_points2d, final_resampled_extra_data = resample_points_based_on_shared_views(
            original_points2d, original_extra_data, number_of_samples_to_return=number_of_samples_full
        )
        self.final_adjustments(points2d=final_resampled_points2d,
                               extra_data=final_resampled_extra_data,
                               error_threshold=dynamic_error_threshold,
                               function_tolerance=function_tolerance,
                               max_number_function_evals=max_number_function_evals,
                               verbose=verbose)

        final_error = self.get_mean_reprojection_error(final_resampled_points2d, median=True)
        if verbose:
            print("Final error: ", final_error)

        return float(final_error)



    def final_adjustments(self,
                          points2d: np.ndarray,
                          extra_data: dict[str, Any],
                          error_threshold: float,
                          function_tolerance: float,
                          max_number_function_evals: int,
                          verbose: bool) -> None:
        """Perform final adjustments and bundle adjustment with a potentially updated threshold.

        Args:
            points2d (np.ndarray): Resampled 2D points.
            extra_data (Dict[str, Any]): Resampled extra data.
            error_threshold (float): Error threshold for filtering good points.
            function_tolerance (float): Tolerance for function convergence in bundle adjustment.
            max_number_function_evals (int): Maximum number of function evaluations in bundle adjustment.
            verbose (bool): If True, prints detailed logs during execution.
        """
        triangulated_points3d = self.triangulate(points2d)
        errors_full = self.calculate_reprojection_error(
            triangulated_points3d, points2d, mean=False
        )
        normalized_errors = self.calculate_reprojection_error(
            triangulated_points3d, points2d, mean=True
        )
        error_dict = get_error_dict(errors_full)
        if verbose:
            logger.debug("Error dictionary after final adjustments", error_dict)

        max_error, min_error = calculate_error_bounds(error_dict)
        dynamic_error_threshold = max(max(max_error, error_threshold), min_error)
        good_points_mask = normalized_errors < dynamic_error_threshold
        filtered_extra_data = subset_extra(extra_data, good_points_mask)

        self.bundle_adjust_points2d(
            points2d[:, good_points_mask],
            filtered_extra_data,
            loss="linear",
            function_tolerance=function_tolerance,
            maximum_number_function_evals=max(200, max_number_function_evals),
            verbose=verbose,
        )

    def bundle_adjust_points2d(
            self,
            points2d: np.ndarray,
            extra_data: dict[str, Any] = None,
            loss: str = "linear",
            threshold: float = 50.0,
            function_tolerance: float = 1e-4,
            maximum_number_function_evals: int = 1000,
            weights: np.ndarray|None = None,
            start_params: np.ndarray|None = None,
            verbose: bool = True,
    ) -> float:
        """Perform bundle adjustment to fine-tune camera parameters.

        Args:
            points2d (np.ndarray): A CxNx2 array of 2D points, where C is the number of cameras
                and N is the number of points.
            extra_data (Optional[Dict[str, Any]]): Optional dictionary containing additional data
                such as 'ids'.
            loss (str): Loss function to use in optimization. Default is 'linear'.
            threshold (float): Scaling factor for the residuals.
            function_tolerance (float): Tolerance for function convergence in optimization.
            maximum_number_function_evals (int): Maximum number of function evaluations.
            weights (Optional[np.ndarray]): Optional weights for the points.
            start_params (Optional[np.ndarray]): Optional initial parameter estimates.
            verbose (bool): If True, prints detailed logs during execution.

        Returns:
            float: Final mean reprojection error after adjustments.
        """
        # Validate input shapes
        if not points2d.ndim == 3 and points2d.shape[2] == 2:
            raise ValueError("points2d must be a CxNx2 array")
        if not  points2d.shape[0] == len(self.cameras):
            raise ValueError(
                f"Invalid points shape, expected first dimension to be equal to "
                f"number of cameras ({len(self.cameras)}), but got shape {points2d.shape}"
            )

        # Update extra_data data if provided, specifically remapping IDs
        if extra_data is not None and 'ids' in extra_data:
            extra_data["ids_map"] = remap_ids(extra_data["ids"])

        # Initialize parameters for bundle adjustment
        initial_params, num_camera_params = self._initalize_bundle_adjust_parameters(points2d, extra_data)

        # Override initial parameters if start_params are provided
        if start_params is not None:
            initial_params = start_params
            num_camera_params = len(self.cameras[0].get_params())

        # Define error function and sparsity pattern for optimization

        jac_sparsity = self._calculate_bundle_adjustment_jacobian_sparsity(points2d, num_camera_params, extra_data)

        # Set up optimization options
        optimization_result = optimize.least_squares(
            fun=self._bundle_adjust_error_function,
            x0=initial_params,
            jac_sparsity=jac_sparsity,
            f_scale=threshold,
            x_scale="jac",
            loss=loss,
            ftol=function_tolerance,
            method="trf",
            tr_solver="lsmr",
            verbose=2 * verbose,
            max_nfev=maximum_number_function_evals,
            args=(points2d, num_camera_params, extra_data),
        )

        # Update camera parameters with optimized results
        optimized_params = optimization_result.x
        for i, camera in enumerate(self.cameras):
            start_idx = i * num_camera_params
            end_idx = (i + 1) * num_camera_params
            camera.set_params(optimized_params[start_idx:end_idx])

        # Calculate and return the mean reprojection error
        mean_error = self.get_mean_reprojection_error(points2d)
        return float(mean_error)

    @jit(parallel=True, forceobj=True)
    def _bundle_adjust_error_function(self, params, points2d, n_cam_params, extra):
        """Error function for bundle adjustment"""
        good = ~np.isnan(points2d)
        n_cams = len(self.cameras)

        for i in range(n_cams):
            cam = self.cameras[i]
            a = i * n_cam_params
            b = (i + 1) * n_cam_params
            cam.set_params(params[a:b])

        n_cams = len(self.cameras)
        sub = n_cam_params * n_cams
        n3d = points2d.shape[1] * 3
        p3ds_test = params[sub: sub + n3d].reshape(-1, 3)
        errors = self.calculate_reprojection_error(p3ds_test, points2d)
        errors_reproj = errors[good]

        if extra is not None:
            ids = extra["ids_map"]
            objp = extra["objp"]
            min_scale = np.min(objp[objp > 0])
            n_boards = int(np.max(ids)) + 1
            a = sub + n3d
            rvecs = params[a: a + n_boards * 3].reshape(-1, 3)
            tvecs = params[a + n_boards * 3: a + n_boards * 6].reshape(-1, 3)
            expected = transform_points(objp, rvecs[ids], tvecs[ids])
            errors_obj = 2 * (p3ds_test - expected).ravel() / min_scale
        else:
            errors_obj = np.array([])

        return np.hstack([errors_reproj, errors_obj])

    def _calculate_bundle_adjustment_jacobian_sparsity(self,
                                                       points2d: np.ndarray,
                                                       number_of_camear_parameters: int,
                                                       extra: dict[str, Any] | None = None) -> dok_matrix:
        """Given an CxNx2 array of 2D points,
        where N is the number of points and C is the number of cameras,
        compute the sparsity structure of the jacobian for bundle adjustment"""

        point_indices = np.zeros(points2d.shape, dtype="int32")
        cam_indices = np.zeros(points2d.shape, dtype="int32")

        for i in range(points2d.shape[1]):
            point_indices[:, i] = i

        for j in range(points2d.shape[0]):
            cam_indices[j] = j

        good = ~np.isnan(points2d)

        if extra is not None:
            ids = extra["ids_map"]
            n_boards = int(np.max(ids)) + 1
            total_board_params = n_boards * (3 + 3)  # rvecs + tvecs
        else:
            n_boards = 0
            total_board_params = 0

        n_cams = points2d.shape[0]
        n_points = points2d.shape[1]
        total_params_reproj = n_cams * number_of_camear_parameters + n_points * 3
        n_params = total_params_reproj + total_board_params

        n_good_values = np.sum(good)
        if extra is not None:
            n_errors = n_good_values + n_points * 3
        else:
            n_errors = n_good_values

        A_sparse = dok_matrix((n_errors, n_params), dtype="int16")

        cam_indices_good = cam_indices[good]
        point_indices_good = point_indices[good]

        # -- reprojection error --
        ix = np.arange(n_good_values)

        ## update camera params based on point error
        for i in range(number_of_camear_parameters):
            A_sparse[ix, cam_indices_good * number_of_camear_parameters + i] = 1

        ## update point position based on point error
        for i in range(3):
            A_sparse[ix, n_cams * number_of_camear_parameters + point_indices_good * 3 + i] = 1

        # -- match for the object points--
        if extra is not None:
            point_ix = np.arange(n_points)

            ## update all the camera parameters
            # A_sparse[n_good_values:n_good_values+n_points*3,
            #          0:n_cams*n_cam_params] = 1

            ## update board rotation and translation based on error from expected
            for i in range(3):
                for j in range(3):
                    A_sparse[
                        n_good_values + point_ix * 3 + i,
                        total_params_reproj + ids * 3 + j,
                    ] = 1
                    A_sparse[
                        n_good_values + point_ix * 3 + i,
                        total_params_reproj + n_boards * 3 + ids * 3 + j,
                    ] = 1

            ## update point position based on error from expected
            for i in range(3):
                A_sparse[
                    n_good_values + point_ix * 3 + i,
                    n_cams * number_of_camear_parameters + point_ix * 3 + i,
                ] = 1

        return A_sparse

    def _initalize_bundle_adjust_parameters(self, points2d:np.ndarray, extra_data:dict[str, Any] | None):
        """Given an CxNx2 array of 2D points,
        where N is the number of points and C is the number of cameras,
        initializes the parameters for bundle adjustment"""

        cam_params = np.hstack([cam.get_params() for cam in self.cameras])
        n_cam_params = len(cam_params) // len(self.cameras)

        total_cam_params = len(cam_params)

        n_cams, n_points, _ = points2d.shape
        assert n_cams == len(self.cameras), (
            "number of cameras in CameraGroup does not " "match number of cameras in 2D points given"
        )

        p3ds = self.triangulate(points2d)

        if extra_data is not None:
            ids = extra_data["ids_map"]
            n_boards = int(np.max(ids[~np.isnan(ids)])) + 1
            total_board_params = n_boards * (3 + 3)  # rvecs + tvecs

            # initialize to 0
            rvecs = np.zeros((n_boards, 3), dtype="float64")
            tvecs = np.zeros((n_boards, 3), dtype="float64")

            if "rvecs" in extra_data and "tvecs" in extra_data:
                rvecs_all = extra_data["rvecs"]
                tvecs_all = extra_data["tvecs"]
                for board_num in range(n_boards):
                    point_id = np.where(ids == board_num)[0][0]
                    cam_ids_possible = np.where(~np.isnan(points2d[:, point_id, 0]))[0]
                    cam_id = np.random.choice(cam_ids_possible)
                    M_cam = self.cameras[cam_id].get_extrinsics_mat()
                    M_board_cam = make_M(rvecs_all[cam_id, point_id], tvecs_all[cam_id, point_id])
                    M_board = np.matmul(inverse(M_cam), M_board_cam)
                    rvec, tvec = get_rtvec(M_board)
                    rvecs[board_num] = rvec
                    tvecs[board_num] = tvec

        else:
            total_board_params = 0

        x0 = np.zeros(total_cam_params + p3ds.size + total_board_params)
        x0[:total_cam_params] = cam_params
        x0[total_cam_params: total_cam_params + p3ds.size] = p3ds.ravel()

        if extra_data is not None:
            start_board = total_cam_params + p3ds.size
            x0[start_board: start_board + n_boards * 3] = rvecs.ravel()
            x0[start_board + n_boards * 3: start_board + n_boards * 6] = tvecs.ravel()

        return x0, n_cam_params


    def get_mean_reprojection_error(self, points2d, median=False):
        triangulated_points3d = self.triangulate(points2d)
        errors = self.calculate_reprojection_error(triangulated_points3d, points2d, mean=True)
        if median:
            return np.median(errors)
        else:
            return np.mean(errors)
