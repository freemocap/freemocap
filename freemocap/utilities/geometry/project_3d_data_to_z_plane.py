import numpy as np


def project_3d_data_to_z_plane(skel3d_frame_marker_xyz: np.ndarray) -> np.ndarray:
    projected_skel3d_frame_marker_xyz = np.zeros(skel3d_frame_marker_xyz.shape)

    projected_skel3d_frame_marker_xyz[:, :, 0] = skel3d_frame_marker_xyz[:, :, 0]
    projected_skel3d_frame_marker_xyz[:, :, 1] = skel3d_frame_marker_xyz[:, :, 1]
    projected_skel3d_frame_marker_xyz[:, :, 2] = 0

    return projected_skel3d_frame_marker_xyz
