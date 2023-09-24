import numpy as np


def rotate_by_90_degrees_around_x_axis(raw_skel3d_frame_marker_xyz: np.ndarray) -> np.ndarray:
    if len(raw_skel3d_frame_marker_xyz.shape) != 3:
        raise ValueError("raw_skel3d_frame_marker_xyz must have shape (N, M, 3)")

    swapped_skel3d_frame_marker_xyz = np.zeros(raw_skel3d_frame_marker_xyz.shape)

    swapped_skel3d_frame_marker_xyz[:, :, 0] = raw_skel3d_frame_marker_xyz[:, :, 0]
    swapped_skel3d_frame_marker_xyz[:, :, 1] = raw_skel3d_frame_marker_xyz[:, :, 2]
    swapped_skel3d_frame_marker_xyz[:, :, 2] = -raw_skel3d_frame_marker_xyz[:, :, 1]

    return swapped_skel3d_frame_marker_xyz
