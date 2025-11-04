import cv2
import numpy as np

from freemocap.core.tasks.calibration_task.ooooold.calibration_helpers.calibration_numpy_types import \
    RotationVectorArray, \
    TranslationVectorArray, ObjectPoints3D


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


def transform_points(points: ObjectPoints3D,
                     rotation_vector: RotationVectorArray,
                     translation_vector: TranslationVectorArray):
    """Rotate points by given rotation vectors and translate.
    Rodrigues' rotation formula is used.
    """
    theta = np.linalg.norm(rotation_vector, axis=1)[:, np.newaxis]
    with np.errstate(invalid="ignore"):
        v = rotation_vector / theta
        v = np.nan_to_num(v)
    dot = np.sum(points * v, axis=1)[:, np.newaxis]
    cos_theta = np.cos(theta)
    sin_theta = np.sin(theta)

    rotated = cos_theta * points + sin_theta * np.cross(v, points) + dot * (1 - cos_theta) * v

    return rotated + translation_vector


def construct_camera_extrinsics_matrix(rotation_vector: RotationVectorArray,
                                       translation_vector: TranslationVectorArray) -> np.ndarray:
    if rotation_vector.shape != (3,) or translation_vector.shape != (3,):
        raise ValueError("Rotation vector and translation vector must have shape (3,)")
    extrinsics_matrix = np.zeros((4, 4))
    rotmat, _ = cv2.Rodrigues(rotation_vector)
    extrinsics_matrix[:3, :3] = rotmat
    extrinsics_matrix[:3, 3] = translation_vector.flatten()
    extrinsics_matrix[3, 3] = 1
    return extrinsics_matrix


def get_rotation_and_translation_vector_from_extrinsics_matrix(extrinsics_matrix: np.ndarray) -> tuple[
    np.ndarray, np.ndarray]:
    if extrinsics_matrix.shape != (4, 4):
        raise ValueError("Extrinsics matrix must be a 4x4 matrix")
    rotation_vector = cv2.Rodrigues(extrinsics_matrix[:3, :3])[0].flatten()
    translation_vector = extrinsics_matrix[:3, 3].flatten()
    return rotation_vector, translation_vector


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
