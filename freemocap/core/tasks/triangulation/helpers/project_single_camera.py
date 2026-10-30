"""Project a single camera's 2D observations onto the Y=0 plane as 3D.

When only one camera is available, DLT triangulation is impossible.
Instead, we map 2D image coordinates to the XZ plane: (u, v) -> (u, 0, v_max - v)
to place the person right-side up on the ground plane with positive Z.
This produces a TriangulationResult-shaped output so downstream code
(filters, skeleton constraints, export) runs identically to the multi-camera
path — it sees the same data shapes and doesn't care about the origin.
"""

import numpy as np
from skellyforge.core.data_tensors.channel_values import ChannelValues, SPATIAL_COMPONENTS
from numpy.typing import NDArray

from freemocap.core.tasks.triangulation.helpers.triangulation_result import TriangulationResult
from freemocap.core.tracking.observation_arrays import observation_arrays


def project_2d_observation_to_3d(
    *,
    observation,  # skellytracker.core.data_primitives.observation.Observation
) -> ChannelValues:
    """Project a single camera's per-frame observation to 3D on the Y=0 plane.

    Returns {point_name: ndarray(3,)} — the same shape as the ``points`` dict
    try_angulate() produces for multi-camera triangulation.
    """
    points = observation_arrays(observation)
    xy = points.image_coordinates
    names = points.point_names
    h, w = observation.image_size  # (height, width) in pixels

    # Strip the stage prefix that Observation.to_keypoints() adds ("body.nose" → "nose")
    values = np.column_stack((xy[:, 0] - w / 2, np.zeros(len(xy)), h - xy[:, 1]))
    return ChannelValues(tuple(name.split(".", 1)[-1] for name in names), values,
                         ~np.isnan(xy).any(axis=-1), component_names=SPATIAL_COMPONENTS)



def project_2d_batch_to_3d(
    *,
    data2d: NDArray[np.float64],  # (n_frames, n_points, 2)
) -> TriangulationResult:
    """Project a single camera's multi-frame 2D data to 3D on the Y=0 plane.

    Returns a TriangulationResult with:
      - points_3d: (n_frames, n_points, 3) with (u, 0, v_max - v) mapping
      - per_camera_weights: (n_frames, n_points, 1) all 1.0
      - reprojection_error: (1, n_frames, n_points) all 0.0
    """
    if data2d.ndim != 3 or data2d.shape[2] != 2:
        raise ValueError(
            f"Expected data2d of shape (n_frames, n_points, 2), got {data2d.shape}"
        )

    n_frames, n_points, _ = data2d.shape
    points_3d = np.zeros((n_frames, n_points, 3), dtype=np.float64)
    u_mid = (np.nanmax(data2d[..., 0]) + np.nanmin(data2d[..., 0])) / 2
    points_3d[..., 0] = data2d[..., 0] - u_mid  # X = u - frame center
    points_3d[..., 1] = 0.0                                           # Y = 0
    v_max = np.nanmax(data2d[..., 1])  # bottom of detected region
    points_3d[..., 2] = v_max - data2d[..., 1]  # Z = v_max - v (flip + shift → positive Z)

    nan_mask = np.isnan(data2d).any(axis=2)
    points_3d[nan_mask] = np.nan

    return TriangulationResult(
        points_3d=points_3d,
        per_camera_weights=np.ones((n_frames, n_points, 1), dtype=np.float64),
        reprojection_error=np.zeros((1, n_frames, n_points), dtype=np.float64),
        diagnostics=None,
    )
