import numpy as np


def project_3d_data_to_z_plane(skel3d_frame_marker_xyz: np.ndarray) -> np.ndarray:
    projected_skel3d_frame_marker_xyz = skel3d_frame_marker_xyz.copy()
    projected_skel3d_frame_marker_xyz[:, :, 2] = 0

    return projected_skel3d_frame_marker_xyz
