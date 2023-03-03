import numpy as np


def flatten_3d_data(skel3d_frame_marker_xyz: np.ndarray) -> np.ndarray:

    flattened_skel3d_frame_marker_xyz = np.zeros(skel3d_frame_marker_xyz.shape)

    flattened_skel3d_frame_marker_xyz[:, :, 0] = skel3d_frame_marker_xyz[:, :, 0]
    flattened_skel3d_frame_marker_xyz[:, :, 1] = 0
    flattened_skel3d_frame_marker_xyz[:, :, 2] = -skel3d_frame_marker_xyz[:, :, 1]

    return flattened_skel3d_frame_marker_xyz
