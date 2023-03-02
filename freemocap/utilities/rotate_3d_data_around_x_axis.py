import logging
import numpy as np

from freemocap.utilities.get_rotation_matrix import get_rotation_matrix

logger = logging.getLogger(__name__)


def rotate_3d_data_around_x_axis(raw_skel3d_frame_marker_xyz: np.ndarray, x_rotation_degrees: int) -> np.ndarray:
    rotation_matrix = get_rotation_matrix(theta1=x_rotation_degrees,
                                          theta2=0,
                                          theta3=0,
                                          order="xyz")

    rotated_skel3d_frame_marker_xyz = np.zeros(raw_skel3d_frame_marker_xyz.shape)

    for frame in range(raw_skel3d_frame_marker_xyz.shape[0]):

        rotated_skel3d_frame_marker_xyz[frame] = np.matmul(raw_skel3d_frame_marker_xyz[frame], rotation_matrix)

        logger.info(f"Rotated frame {frame} of {raw_skel3d_frame_marker_xyz.shape[0]}")
        logger.info(f"Input data: {raw_skel3d_frame_marker_xyz[frame][0][:]}")
        logger.info(f"Output data: {rotated_skel3d_frame_marker_xyz[frame][0][:]}")

    return rotated_skel3d_frame_marker_xyz
