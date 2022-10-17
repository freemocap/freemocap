from pathlib import Path
from typing import Union

import logging

import numpy as np

logger = logging.getLogger(__name__)


def load_raw_mediapipe3d_data(output_data_folder_path: Union[str, Path]):
    mediapipe3d_xyz_file_path = (
        Path(output_data_folder_path)
        / "raw_data"
        / "mediapipe_3dData_numFrames_numTrackedPoints_spatialXYZ.npy"
    )
    logger.info(f"loading: {mediapipe3d_xyz_file_path}")
    mediapipe_3dData_numFrames_numTrackedPoints_spatialXYZ = np.load(
        str(mediapipe3d_xyz_file_path)
    )

    return mediapipe_3dData_numFrames_numTrackedPoints_spatialXYZ


def load_post_processed_mediapipe3d_data(output_data_folder_path: Union[str, Path]):
    mediapipe3d_xyz_file_path = (
        Path(output_data_folder_path)
        / "post_processed_data"
        / "mediaPipeSkel_3d_origin_aligned.npy"
    )
    logger.info(f"loading: {mediapipe3d_xyz_file_path}")
    mediapipe_3dData_numFrames_numTrackedPoints_spatialXYZ = np.load(
        str(mediapipe3d_xyz_file_path)
    )

    return mediapipe_3dData_numFrames_numTrackedPoints_spatialXYZ


def load_skeleton_reprojection_error_data(output_data_folder_path: Union[str, Path]):
    mediapipe3d_reprojection_error_file_path = (
        Path(output_data_folder_path)
        / "raw_data"
        / "mediapipe_3dData_numFrames_numTrackedPoints_reprojectionError.npy"
    )
    logger.info(f"loading: {mediapipe3d_reprojection_error_file_path}")
    mediapipe_3dData_numFrames_numTrackedPoints_reprojectionError = np.load(
        str(mediapipe3d_reprojection_error_file_path)
    )

    return mediapipe_3dData_numFrames_numTrackedPoints_reprojectionError
