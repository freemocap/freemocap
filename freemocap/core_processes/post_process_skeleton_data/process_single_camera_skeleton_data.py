import logging
from pathlib import Path
from typing import Tuple, Union

import numpy as np

from freemocap.core_processes.capture_volume_calibration.save_3d_data_to_npy import (
    save_3d_data_to_npy,
)
from freemocap.utilities.geometry.project_3d_data_to_z_plane import project_3d_data_to_z_plane

logger = logging.getLogger(__name__)


def process_single_camera_skeleton_data(
    input_image_data_frame_marker_xyz: np.ndarray,
    raw_data_folder_path: Union[str, Path],
    file_prefix: str = "",
    project_to_z_plane: bool = True,
) -> Tuple[np.ndarray, np.ndarray]:
    skeleton_reprojection_error_fr_mar = np.zeros(input_image_data_frame_marker_xyz.shape[0:2])
    skeleton_reprojection_error_cam_fr_mar = np.zeros(
        (1, input_image_data_frame_marker_xyz.shape[0], input_image_data_frame_marker_xyz.shape[1])
    )
    if project_to_z_plane:
        logger.info("Altering image-derived 3d data to resemble multi-camera reconstructed data.")

        raw_skel3d_frame_marker_xyz = project_3d_data_to_z_plane(
            skel3d_frame_marker_xyz=input_image_data_frame_marker_xyz
        )
    else:
        raw_skel3d_frame_marker_xyz = input_image_data_frame_marker_xyz

    save_3d_data_to_npy(
        data3d_numFrames_numTrackedPoints_XYZ=raw_skel3d_frame_marker_xyz,
        data3d_numFrames_numTrackedPoints_reprojectionError=skeleton_reprojection_error_fr_mar,
        data3d_numCams_numFrames_numTrackedPoints_reprojectionError=skeleton_reprojection_error_cam_fr_mar,
        path_to_folder_where_data_will_be_saved=raw_data_folder_path,
        processing_level="raw",
        file_prefix=file_prefix,
    )

    return raw_skel3d_frame_marker_xyz, skeleton_reprojection_error_fr_mar
