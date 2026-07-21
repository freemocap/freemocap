from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(slots=True, frozen=True)
class TriangulationResult:
    """Output of `Triangulator.triangulate(...)`.

    Hot path - slots removes per-instance __dict__ overhead, frozen makes it
    immutable so it can be shared across threads/queues without copying.

    Shape conventions:
        - Single-frame input (data2d shape (n_cameras, n_points, 2)):
            points_3d: (n_points, 3)
            per_camera_weights: (n_points, n_cameras)
            reprojection_error: (n_cameras, n_points)
        - Batch input (dict / 4D array):
            points_3d: (n_frames, n_points, 3)
            per_camera_weights: (n_frames, n_points, n_cameras)
            reprojection_error: (n_cameras, n_frames, n_points)

    NaN encodes 'no observation' (where the input 2D was NaN) or 'insufficient
    cameras to triangulate' (fewer than minimum_cameras_for_triangulation valid
    observations for that point).

    When `use_outlier_rejection=False`, per_camera_weights is uniform
    1/n_valid_cameras for valid cameras and NaN for cameras with no observation.
    When True, weights are the ensemble-weighted per-camera confidences.
    """

    points_3d: NDArray[np.float64]
    per_camera_weights: NDArray[np.float64]
    reprojection_error: NDArray[np.float64]
