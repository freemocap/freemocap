"""Pure-numpy triangulation primitives.

These functions are the single source of triangulation math used everywhere
in the codebase. They operate on undistorted-normalized 2D coordinates and
[R|t] (3x4) extrinsics matrices.

Ported from the recently-added subset-ensemble outlier-rejection routine
in `OLD-capture_volume_calibration/anipose_camera_calibration/freemocap_anipose.py`.
Algorithm unchanged; only signatures, naming, and type hints were updated.
"""
import itertools

import numpy as np
from numpy.typing import NDArray

from freemocap.core.tasks.triangulation.helpers.default_triangulation_values import DEFAULT_MIN_CAMERAS, \
    DEFAULT_MAX_CAMERAS_TO_DROP, DEFAULT_TARGET_REPROJECTION_ERROR
from freemocap.core.tasks.triangulation.helpers.project_point_to_camera import project_point_to_camera
from freemocap.core.tasks.triangulation.helpers.triangulate_simple import triangulate_simple

_WEIGHT_DECAY_K: float = 5.0


def triangulate_with_outlier_rejection(
    *,
    points_2d: NDArray[np.float64],
    extrinsics_mats: NDArray[np.float64],
    minimum_cameras_for_triangulation: int = DEFAULT_MIN_CAMERAS,
    maximum_cameras_to_drop: int = DEFAULT_MAX_CAMERAS_TO_DROP,
    target_reprojection_error: float = DEFAULT_TARGET_REPROJECTION_ERROR,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Triangulate one 3D point with progressive subset-ensemble outlier rejection.

    Triangulates using all valid cameras; if reprojection error exceeds target,
    iteratively tests camera subsets (dropping 1..max_drop cameras) and returns
    an exponentially-weighted ensemble average plus per-camera confidence weights.

    Args:
        points_2d: shape (N, 2) - undistorted-normalized 2D detections from N cameras.
        extrinsics_mats: shape (N, 3, 4) - [R|t] matrices for those N cameras.
        minimum_cameras_for_triangulation: minimum cameras required for any subset.
        maximum_cameras_to_drop: maximum cameras to drop while searching for subsets.
        target_reprojection_error: target mean reprojection error in normalized
            coords (~0.01); also drives the exp(-5 * error / target) weighting.

    Returns:
        (point_3d_xyz, normalized_camera_weights):
            - point_3d_xyz: shape (3,) - 3D point in world coordinates.
            - normalized_camera_weights: shape (N,) - per-camera confidence weights
              that sum to 1.0 across all subsets (uniform 1.0 if baseline already
              meets target_reprojection_error).
    """
    total_valid_cams = len(extrinsics_mats)
    local_indices = list(range(total_valid_cams))
    normalized_camera_weights = np.zeros(total_valid_cams, dtype=np.float64)

    default_p3d = triangulate_simple(points=points_2d, extrinsics_mats=extrinsics_mats)
    default_proj = np.array(
        [
            project_point_to_camera(point_3d=default_p3d, extrinsics_mat=mat)
            for mat in extrinsics_mats
        ]
    )
    default_errors = np.linalg.norm(default_proj - points_2d, axis=1)
    default_mean_error = float(np.mean(default_errors))

    if default_mean_error < target_reprojection_error:
        normalized_camera_weights[:] = 1.0
        return default_p3d, normalized_camera_weights

    best_p3d, best_error = default_p3d, default_mean_error
    best_camera_combo: list[int] = list(local_indices)

    default_weight = float(np.exp(-_WEIGHT_DECAY_K * default_mean_error / target_reprojection_error))
    weighted_p3d_sum = default_weight * default_p3d
    total_weight = default_weight
    normalized_camera_weights[:] += default_weight

    for camera_drop_count in range(1, maximum_cameras_to_drop + 1):
        selected_camera_count = total_valid_cams - camera_drop_count
        if selected_camera_count < minimum_cameras_for_triangulation:
            break

        combinations = list(itertools.combinations(local_indices, selected_camera_count))
        for combo in combinations:
            kept_local_indices = list(combo)
            candidate_pts = points_2d[kept_local_indices]
            candidate_cams = extrinsics_mats[kept_local_indices]

            candidate_p3d = triangulate_simple(
                points=candidate_pts, extrinsics_mats=candidate_cams,
            )
            candidate_proj = np.array(
                [
                    project_point_to_camera(point_3d=candidate_p3d, extrinsics_mat=mat)
                    for mat in candidate_cams
                ]
            )
            candidate_errors = np.linalg.norm(candidate_proj - candidate_pts, axis=1)
            candidate_mean_error = float(np.mean(candidate_errors))

            weight = float(np.exp(-_WEIGHT_DECAY_K * candidate_mean_error / target_reprojection_error))
            weighted_p3d_sum = weighted_p3d_sum + weight * candidate_p3d
            total_weight += weight
            normalized_camera_weights[kept_local_indices] += weight

            if candidate_mean_error < best_error:
                best_error = candidate_mean_error
                best_p3d = candidate_p3d
                best_camera_combo = kept_local_indices

        if best_error < target_reprojection_error:
            break

    if total_weight > 1e-12:
        weighted_p3d = weighted_p3d_sum / total_weight
        normalized_camera_weights /= total_weight
    else:
        weighted_p3d = best_p3d
        normalized_camera_weights[:] = 0.0
        normalized_camera_weights[best_camera_combo] = 1.0

    if best_error < default_mean_error:
        return weighted_p3d, normalized_camera_weights

    normalized_camera_weights[:] = 1.0
    return default_p3d, normalized_camera_weights
