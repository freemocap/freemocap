# Most of this was copied (with permission) from the original `aniposelib` package (https://github.com/lambdaloop/aniposelib), and we're adapting it to our needs here. M
# ore info on Anipoise: https://anipose.readthedocs.io/en/latest/

import logging
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from numba import jit
from scipy import optimize
from scipy.linalg import inv as inverse
from scipy.sparse import dok_matrix
from skellycam import CameraId
from tqdm import trange

logger = logging.getLogger(__name__)


@jit(nopython=True, parallel=False)
def anipose_triangulate_simple(points2d: np.ndarray, camera_matrices: np.ndarray) -> np.ndarray:
    """
    Triangulate 3D point from 2D points and camera matrices using the Direct Linear Transform (DLT) method.

    :param points2d: A 2D array of shape (N, 2), where N is the number of cameras. Each row represents the
                     2D coordinates (x, y) of the point in the image plane of each camera.
    :param camera_matrices: A 3D array of shape (N, 3, 4), where each element is a 3x4 camera projection matrix.
    :return: A 1D array of shape (3,) representing the triangulated 3D point.
    """

    num_cams = camera_matrices.shape[0]
    A = np.zeros((num_cams * 2, 4))

    for i in range(num_cams):
        x, y = points2d[i]
        mat = camera_matrices[i]
        A[i * 2] = x * mat[2] - mat[0]
        A[i * 2 + 1] = y * mat[2] - mat[1]

    _, _, vh = np.linalg.svd(A, full_matrices=False) #CHECK - Ai said this could be set to False since " we only need the right singular vectors, which is more efficient." but we should check on this bc I don't know what that means lol

    points3d_xyzh = vh[-1]
    points3d_xyzh /= points3d_xyzh[3]  # Normalize the last element to 1

    return points3d_xyzh[:3]

def calculate_error_bounds(error_dict: dict[tuple[int, int], tuple[int, np.ndarray]]) -> tuple[float, float]:
    """Calculate the maximum and minimum error bounds from an error dictionary.

    Args:
        error_dict (Dict[Tuple[int, int], Tuple[int, np.ndarray]]): Dictionary containing error statistics
            for camera pairs, where the key is a tuple of camera indices and the value is a tuple of
            (number of observations, percentiles).

    Returns:
        Tuple[float, float]: A tuple of (max_error, min_error) based on the percentiles of error means.
    """
    max_error = 0.0
    min_error = float('inf')
    for _, (_, percents) in error_dict.items():
        max_error = max(percents[-1], max_error)
        min_error = min(percents[0], min_error)
    return max_error, min_error


def transform_points(points, rotation_vectors, translation_vectors):
    """Rotate points by given rotation vectors and translate.
    Rodrigues' rotation formula is used.
    """
    theta = np.linalg.norm(rotation_vectors, axis=1)[:, np.newaxis]
    with np.errstate(invalid="ignore"):
        v = rotation_vectors / theta
        v = np.nan_to_num(v)
    dot = np.sum(points * v, axis=1)[:, np.newaxis]
    cos_theta = np.cos(theta)
    sin_theta = np.sin(theta)

    rotated = cos_theta * points + sin_theta * np.cross(v, points) + dot * (1 - cos_theta) * v

    return rotated + translation_vectors

def remap_ids(ids: np.ndarray|list[int]) -> np.ndarray:
    """
    Remap the unique identifiers in the input array to a consecutive range starting from zero.

    :param ids: An array-like structure containing the original identifiers.
    :return: A NumPy array with the identifiers remapped to a consecutive range.
    """
    ids_array = np.asarray(ids)
    unique_ids, remapped_ids = np.unique(ids_array, return_inverse=True)
    return remapped_ids


def subset_extra_data(extra_data: dict[str, Any], indices: np.ndarray) -> dict[str, Any]:
    """
    Subset the extra data dictionary based on the selected indices.

    :param extra_data: The dictionary containing extra data.
    :param indices: The indices to subset the data.
    :return: A new dictionary with data subset according to the provided indices.
    """
    if not extra_data:
        return extra_data
    return {key: value[indices] for key, value in extra_data.items() if key in extra_data}

def resample_points_based_on_shared_views(points2d: np.ndarray,
                                          extra_data: dict[str, Any],
                                          number_of_samples_to_return: int = 25) -> tuple[np.ndarray, dict[str, Any] | None]:
    """
    Resample 2D points to prioritize those seen by multiple cameras.

    :param points2d: A 3D array of shape (N_cams, N_points, 2) containing 2D points for each camera.
                     NaN values represent missing data for a camera.
    :param extra_data: Optional dictionary containing additional data (like {'objp', 'ids', 'rotation_vectors', 'translation_vectors'})
                  that should be resampled in the same way as points2d.
    :param number_of_samples_to_return: The maximum number of points to sample, prioritizing those visible in more cameras.
    :return: A tuple containing the resampled points2d and the resampled extra dictionary.
    """

    n_cams = points2d.shape[0]
    points2d_valid = ~np.isnan(points2d[:, :, 0])  # Boolean array indicating valid (non-NaN) points
    point_indices = np.arange(points2d.shape[1])
    num_cams = np.sum(points2d_valid, axis=0)  # Number of cameras observing each point

    included_points = set()

    # Iterate over each unique pair of cameras
    for first_cam in range(n_cams):
        for second_cam in range(first_cam + 1, n_cams):
            # Determine which points are visible in both selected cameras
            visible_in_both = points2d_valid[first_cam] & points2d_valid[second_cam]
            n_good = np.sum(visible_in_both)

            if n_good > 0:
                # Select points seen by the most cameras, adding a small random value for tie-breaking
                visibility_scores = num_cams[visible_in_both].astype(np.float64)
                visibility_scores += np.random.random(size=visibility_scores.shape)

                # Pick the top n_samp points based on visibility scores
                picked_indices = np.argsort(-visibility_scores)[:number_of_samples_to_return]
                selected_points = point_indices[visible_in_both][picked_indices]

                # Add selected points to the set of included points
                included_points.update(selected_points)

    # Sort the final indices of included points for consistent ordering
    final_indices = sorted(included_points)
    resampled_ponts = points2d[:, final_indices]

    extra_data = subset_extra_data(extra_data, final_indices)

    return resampled_ponts, extra_data

def subset_extra(extra, ixs):
    if extra is None:
        return None

    new_extra = {
        "objp": extra["objp"][ixs],
        "ids": extra["ids"][ixs],
        "rotation_vectors": extra["rotation_vectors"][:, ixs],
        "translation_vectors": extra["translation_vectors"][:, ixs],
    }
    return new_extra


def make_M(rvec, tvec):
    out = np.zeros((4,4))
    rotmat, _ = cv2.Rodrigues(rvec)
    out[:3,:3] = rotmat
    out[:3, 3] = tvec.flatten()
    out[3, 3] = 1
    return out

def get_rtvec(M):
    rvec = cv2.Rodrigues(M[:3, :3])[0].flatten()
    tvec = M[:3, 3].flatten()
    return rvec, tvec

def get_error_dict(errors_full, min_points=10):
    n_cams = errors_full.shape[0]
    errors_norm = np.linalg.norm(errors_full, axis=2)

    good = ~np.isnan(errors_full[:, :, 0])

    error_dict = dict()

    for i in range(n_cams):
        for j in range(i + 1, n_cams):
            subset = good[i] & good[j]
            err_subset = errors_norm[:, subset][[i, j]]
            err_subset_mean = np.mean(err_subset, axis=0)
            if np.sum(subset) > min_points:
                percents = np.percentile(err_subset_mean, [15, 75])
                # percents = np.percentile(err_subset, [25, 75])
                error_dict[(i, j)] = (err_subset.shape[1], percents)
    return error_dict

@dataclass
class AniposeCameraCalibrationEstimate:
    name: str
    camera_id: CameraId
    size: tuple[int, int]
    rotation_vector: np.ndarray  # rodriguez rotation vector relative to Camera#0
    translation_vector: np.ndarray # translation vector relative to Camera#0

    camera_matrix: np.ndarray = np.eye(3, dtype="float64")
    distortion_coefficients: np.ndarray = np.zeros(5),

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

    @property
    def extrinsics_matrix(self) -> np.ndarray:
        """
        Returns the extrinsics matrix of the camera, which is a 4x4 matrix that transforms points from the camera coordinate system to the world coordinate system.
        the left upper 3x3 matrix is the rotation matrix, and the rightmost column is the translation vector.
        the bottom row is [0, 0, 0, 1] (where the 1 is the homogeneous coordinate, which makes the matrix invertible and provides the scale factor for the translation vector to put it in spatial coordinates)
        """

        extrinsics_matrix = np.zeros((4, 4))

        extrinsics_matrix[:3, :3] = cv2.Rodrigues(self.rotation_vector)
        extrinsics_matrix[:3, 3] = self.translation_vector.flatten()
        extrinsics_matrix[3, 3] = 1
        return extrinsics_matrix



    def get_optimizable_parameters(self):
        """
        Grabs the parametesr that will be optimed and organizes them in a numpy array
        :return:
        """
        optimized_parameters = np.zeros(9, dtype="float64")
        optimized_parameters[0:3] = self.rotation_vector
        optimized_parameters[3:6] = self.translation_vector
        optimized_parameters[6] = self.focal_length
        optimized_parameters[7] = self.distortion_coefficients[0]
        optimized_parameters[8] = self.distortion_coefficients[1]
        return optimized_parameters

    def set_optimized_parameters(self, optimized_parameters: np.ndarray):
        """
        Sets camera parameters from optimized parameters


        :param optimized_parameters:
        :return:
        """

        self.rotation_vector = optimized_parameters[0:3]
        self.translation_vector = optimized_parameters[3:6]
        self.focal_length = optimized_parameters[6]

        distortion_coefficients = np.zeros(5)
        distortion_coefficients[0] = optimized_parameters[7]
        distortion_coefficients[1] = optimized_parameters[8]
        self.distortion_coefficients = distortion_coefficients


    def undistort_points(self, points2d: np.ndarray) -> np.ndarray:
        """
        Undistorts 2D points using the camera's intrinsic parameters and distortion coefficients.

        This function adjusts the provided 2D points to account for lens distortion, returning
        points that are mapped as they would appear in an ideal pinhole camera model. The process
        ensures that the ray passing from the nodal point of the camera lens through the
        undistorted 2D point intersects the corresponding 3D point in space accurately.

        :param points2d: A NumPy array of shape (N, 2) or (N, M, 2) representing the 2D points
                         to be undistorted. These are typically the distorted pixel coordinates
                         captured by the camera.
        :return: A NumPy array of the same shape as `points2d` containing the undistorted 2D points.
        """
        shape = points2d.shape
        points2d = points2d.reshape(-1, 1, 2)
        undistorted_points2d = cv2.undistortPoints(points2d, self.camera_matrix.astype("float64"),
                                                   self.distortion_coefficients.astype("float64"))
        return undistorted_points2d.reshape(shape)

    def project_3d_to_2d(self, points3d: np.ndarray) -> np.ndarray:
        if not points3d.shape[-1] == 3:
            raise ValueError("points3d must have shape (N, 3)")
        points3d = points3d.reshape(-1, 1, 3)
        projected_2d_points, _ = cv2.projectPoints(
            points3d,
            self.rotation_vector,
            self.translation_vector,
            self.camera_matrix.astype("float64"),
            self.distortion_coefficients.astype("float64"),
        )
        if projected_2d_points.shape != (points3d.shape[0], 1, 2):
            raise ValueError(f"projected_2d_points has incorrect shape: {projected_2d_points.shape}")

        return projected_2d_points

    def single_camera_reprojection_error(self, points3d:np.ndarray, points2d:np.ndarray) -> np.ndarray:

        projected_points3d = self.project_3d_to_2d(points3d)
        projecting_3d_points_onto_2d_image_plane = projected_points3d.reshape(points2d.shape) #? Should this be np.squeeze(projected_points3d)?
        return points2d - projecting_3d_points_onto_2d_image_plane


@dataclass
class CalibrationInputData:
    pixel_points2d: np.ndarray  # Shape: (N_cams, N_points, 2), px, py pixel coordinates of object points
    object_points3d: np.ndarray  # Shape: (N_points, 3), x, y, z object points in 3D space (corresponding to pixel_points2d)
    ids: np.ndarray  # IDs of points (2d and 3d) for each camera
    rotation_vectors: np.ndarray  # Rotation vectors
    translation_vectors: np.ndarray  # Translation vectors

@dataclass
class AniposeCameraGroupCalibrator:
    camera_calibration_estimates: dict[CameraId, AniposeCameraCalibrationEstimate]
    
    max_iterations: int = 10
    starting_error_threshold: float = 15.0
    ending_error_threshold: float = 1.0
    max_number_function_evals: int = 200
    function_tolerance: float = 1e-4
    number_of_samples_per_iteration: int = 100
    number_of_samples_full: int = 1000
    error_threshold: float = 0.3

    def run_iterative_bundle_adjustment(
            self,
            points2d: np.ndarray,
            extra_data: dict[str, Any],

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
        assert points2d.shape[0] == len(self.camera_calibration_estimates), (
            f"Invalid points shape, expected first dimension to be equal to "
            f"number of cameras ({len(self.camera_calibration_estimates)}), but got shape {points2d.shape}"
        )

        # Initialize
        error_list = []
        original_points2d = points2d
        original_extra_data = extra_data

        # log original error before resampling
        original_error = self.get_mean_reprojection_error(points2d, median=True)
        logger.info(
            f"Starting iterative bundle adjustment...\n Number of cameras: {len(self.camera_calibration_estimates)}\nNumber of points: {points2d.shape[1]}\nOriginal error: {original_error:.2f}")

        # Resample initial set of points to prioritize shared views
        points2d, extra_data = resample_points_based_on_shared_views(
            original_points2d,
            original_extra_data,
            number_of_samples_to_return=self.number_of_samples_full
        )
        initial_error = self.get_mean_reprojection_error(points2d, median=True)

        logger.debug("Initial error after resampling: ", initial_error)

        # Calculate dynamic error thresholds for each iteration
        error_thresholds = np.exp(
            np.linspace(np.log(self.starting_error_threshold), np.log(self.ending_error_threshold), num=self.max_iterations))

        logger.debug(f"Error thresholds we will use for each bundle adjustment iteration: {error_thresholds}")

        # Iterative bundle adjustment
        dynamic_error_threshold = self.starting_error_threshold
        for iteration in range(self.max_iterations):
            resampled_points2d, resampled_extra_data = resample_points_based_on_shared_views(
                original_points2d, original_extra_data, number_of_samples_to_return=self.number_of_samples_full
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
            if current_error < self.error_threshold:

                logger.debug(f"Converged after {iteration + 1} iterations")
                break


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
                function_tolerance=self.function_tolerance,
                maximum_number_function_evals=self.max_number_function_evals,
            )

        # Final adjustments and error calculation
        final_resampled_points2d, final_resampled_extra_data = resample_points_based_on_shared_views(
            original_points2d, original_extra_data, number_of_samples_to_return=self.number_of_samples_full
        )
        self.final_adjustments(points2d=final_resampled_points2d,
                               extra_data=final_resampled_extra_data,
                               error_threshold=dynamic_error_threshold,
)

        final_error = self.get_mean_reprojection_error(final_resampled_points2d, median=True)
        print("Final error: ", final_error)

        return float(final_error)

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
        if not points_2d.shape[0] == len(self.camera_calibration_estimates):
            raise ValueError(
                f"Invalid points shape, first dim of 2D points should be equal to"
                f" number of cameras ({len(self.camera_calibration_estimates)}), but shape is {points_2d.shape}"
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

        for camera_number, cam in enumerate(self.camera_calibration_estimates):
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


    def project_3d_to_2d(self, points3d: np.ndarray):
        """Given an Nx3 array of points, this returns an CxNx2 array of 2D points,
        where C is the number of cameras"""
        points3d = points3d.reshape(-1, 1, 3)
        n_points = points3d.shape[0]
        n_cams = len(self.camera_calibration_estimates)

        projected_points2d = np.empty((n_cams, n_points, 2), dtype="float64")
        for camera_number, camera in enumerate(self.camera_calibration_estimates):
            projected_points2d[camera_number] = camera.project_3d_to_2d(points3d).reshape(n_points, 2)

        # check shape
        assert projected_points2d.shape == (n_cams, n_points,
                                            2), f"Invalid projected_points2d shape, should be {n_cams, n_points, 2}, but shape is {projected_points2d.shape}"

        return projected_points2d

    def triangulate(self, points2d, undistort=True, progress=False):
        """Given an CxNx2 array, this returns an Nx3 array of points,
        where N is the number of points and C is the number of cameras"""

        assert points2d.shape[0] == len(
            self.camera_calibration_estimates
        ), "Invalid points shape, first dim should be equal to" " number of cameras ({}), but shape is {}".format(
            len(self.camera_calibration_estimates), points2d.shape
        )

        one_point = False
        if len(points2d.shape) == 2:
            points2d = points2d.reshape(-1, 1, 2)
            one_point = True

        if undistort:
            new_points = np.empty(points2d.shape)
            for camera_number, camera in enumerate(self.camera_calibration_estimates):
                # must copy in order to satisfy opencv underneath
                sub = np.copy(points2d[camera_number])
                new_points[camera_number] = camera.undistort_points(sub)
            points2d = new_points

        n_cams, n_points, _ = points2d.shape

        triangulated_points3d = np.empty((n_points, 3))
        triangulated_points3d[:] = np.nan

        camera_matricies = np.array([camera.get_extrinsics_mat() for camera in self.camera_calibration_estimates])

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


        if one_point:
            triangulated_points3d = triangulated_points3d[0]

        return triangulated_points3d



    def final_adjustments(self,
                          points2d: np.ndarray,
                          extra_data: dict[str, Any],
                          error_threshold: float,
                          function_tolerance: float,
                          max_number_function_evals: int) -> None:
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
        )

    def bundle_adjust_points2d(
            self,
            points2d: np.ndarray,
            extra_data: dict[str, Any],
            loss: str = "linear",
            threshold: float = 50.0,
            function_tolerance: float = 1e-4,
            maximum_number_function_evals: int = 1000,
            weights: np.ndarray|None = None,
            start_params: np.ndarray|None = None,

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
        if not  points2d.shape[0] == len(self.camera_calibration_estimates):
            raise ValueError(
                f"Invalid points shape, expected first dimension to be equal to "
                f"number of cameras ({len(self.camera_calibration_estimates)}), but got shape {points2d.shape}"
            )

        # Update extra_data data if provided, specifically remapping IDs
        if extra_data is not None and 'ids' in extra_data:
            extra_data["ids_map"] = remap_ids(extra_data["ids"])

        # Initialize parameters for bundle adjustment
        initial_params, num_camera_params = self._initalize_bundle_adjust_parameters(points2d, extra_data)

        # Override initial parameters if start_params are provided
        if start_params is not None:
            initial_params = start_params
            num_camera_params = len(self.camera_calibration_estimates[0].get_optimizable_parameters())

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
            verbose=2 ,
            max_nfev=maximum_number_function_evals,
            args=(points2d, num_camera_params, extra_data),
        )

        # Update camera parameters with optimized results
        optimized_params = optimization_result.x
        for i, camera in enumerate(self.camera_calibration_estimates):
            start_idx = i * num_camera_params
            end_idx = (i + 1) * num_camera_params
            camera.set_params(optimized_params[start_idx:end_idx])

        # Calculate and return the mean reprojection error
        mean_error = self.get_mean_reprojection_error(points2d)
        return float(mean_error)

    @jit(parallel=True, forceobj=True)
    def _bundle_adjust_error_function(self,
                                      optimizable_parameters:np.ndarray,
                                      points2d,
                                      number_of_camera_parameters,
                                      extra):
        """Error function for bundle adjustment"""
        good = ~np.isnan(points2d)
        n_cams = len(self.camera_calibration_estimates)

        for i in range(n_cams):
            cam = self.camera_calibration_estimates[i]
            a = i * number_of_camera_parameters
            b = (i + 1) * number_of_camera_parameters
            cam.set_params(optimizable_parameters[a:b])

        n_cams = len(self.camera_calibration_estimates)
        sub = number_of_camera_parameters * n_cams
        n3d = points2d.shape[1] * 3
        p3ds_test = optimizable_parameters[sub: sub + n3d].reshape(-1, 3)
        errors = self.calculate_reprojection_error(p3ds_test, points2d)
        errors_reproj = errors[good]

        ids = extra["ids_map"]
        objp = extra["objp"]
        min_scale = np.min(objp[objp > 0])
        n_boards = int(np.max(ids)) + 1
        a = sub + n3d
        rotation_vectors = optimizable_parameters[a: a + n_boards * 3].reshape(-1, 3)
        translation_vectors = optimizable_parameters[a + n_boards * 3: a + n_boards * 6].reshape(-1, 3)
        expected = transform_points(objp, rotation_vectors[ids], translation_vectors[ids])
        errors_obj = 2 * (p3ds_test - expected).ravel() / min_scale


        return np.hstack([errors_reproj, errors_obj])

    def _calculate_bundle_adjustment_jacobian_sparsity(self,
                                                       points2d: np.ndarray,
                                                       number_of_camear_parameters: int,
                                                       extra_data: dict[str, Any]) -> dok_matrix:
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


        ids = extra_data["ids_map"]
        n_boards = int(np.max(ids)) + 1
        total_board_params = n_boards * (3 + 3)  # rotation_vectors + translation_vectors

        n_cams = points2d.shape[0]
        n_points = points2d.shape[1]
        total_params_reproj = n_cams * number_of_camear_parameters + n_points * 3
        n_params = total_params_reproj + total_board_params

        n_good_values = np.sum(good)

        n_errors = n_good_values + n_points * 3


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

    def _initalize_bundle_adjust_parameters(self, points2d:np.ndarray, extra_data:dict[str, Any]):
        """Given an CxNx2 array of 2D points,
        where N is the number of points and C is the number of cameras,
        initializes the parameters for bundle adjustment"""

        cam_params = np.hstack([cam.get_opitmizad_parameters() for cam in self.camera_calibration_estimates])
        n_cam_params = len(cam_params) // len(self.camera_calibration_estimates)

        total_cam_params = len(cam_params)

        n_cams, n_points, _ = points2d.shape
        assert n_cams == len(self.camera_calibration_estimates), (
            "number of cameras in CameraGroup does not " "match number of cameras in 2D points given"
        )

        p3ds = self.triangulate(points2d)

        ids = extra_data["ids_map"]
        n_boards = int(np.max(ids[~np.isnan(ids)])) + 1
        total_board_params = n_boards * (3 + 3)  # rotation_vectors + translation_vectors

        # initialize to 0
        rotation_vectors = np.zeros((n_boards, 3), dtype="float64")
        translation_vectors = np.zeros((n_boards, 3), dtype="float64")

        if "rotation_vectors" in extra_data and "translation_vectors" in extra_data:
            rotation_vectors_all = extra_data["rotation_vectors"]
            translation_vectors_all = extra_data["translation_vectors"]
            for board_num in range(n_boards):
                point_id = np.where(ids == board_num)[0][0]
                cam_ids_possible = np.where(~np.isnan(points2d[:, point_id, 0]))[0]
                cam_id = np.random.choice(cam_ids_possible)
                M_cam = self.camera_calibration_estimates[cam_id].extrinsics_matrix
                M_board_cam = make_M(rotation_vectors_all[cam_id, point_id], translation_vectors_all[cam_id, point_id])
                M_board = np.matmul(inverse(M_cam), M_board_cam)
                rvec, tvec = get_rtvec(M_board)
                rotation_vectors[board_num] = rvec
                translation_vectors[board_num] = tvec

        x0 = np.zeros(total_cam_params + p3ds.size + total_board_params)
        x0[:total_cam_params] = cam_params
        x0[total_cam_params: total_cam_params + p3ds.size] = p3ds.ravel()

        if extra_data is not None:
            start_board = total_cam_params + p3ds.size
            x0[start_board: start_board + n_boards * 3] = rotation_vectors.ravel()
            x0[start_board + n_boards * 3: start_board + n_boards * 6] = translation_vectors.ravel()

        return x0, n_cam_params


    def get_mean_reprojection_error(self, points2d, median=False):
        triangulated_points3d = self.triangulate(points2d)
        errors = self.calculate_reprojection_error(triangulated_points3d, points2d, mean=True)
        if median:
            return np.median(errors)
        else:
            return np.mean(errors)
