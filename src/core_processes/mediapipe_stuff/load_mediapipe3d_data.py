import logging
from pathlib import Path
from typing import Union

import numpy as np
from old_src.config.home_dir import MEDIAPIPE_3D_NPY_FILE_NAME, RAW_DATA_FOLDER_NAME

logger = logging.getLogger(__name__)


def load_raw_mediapipe3d_data(output_data_folder_path: Union[str, Path]):
    mediapipe3d_xyz_file_path = (
        Path(output_data_folder_path)
        / RAW_DATA_FOLDER_NAME
        / MEDIAPIPE_3D_NPY_FILE_NAME
    )
    logger.info(f"loading: {mediapipe3d_xyz_file_path}")
    mediapipe_3dData_numFrames_numTrackedPoints_spatialXYZ = np.load(
        str(mediapipe3d_xyz_file_path)
    )

    return mediapipe_3dData_numFrames_numTrackedPoints_spatialXYZ


def load_post_processed_mediapipe3d_data(mediapipe3d_xyz_file_path: Union[str, Path]):

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
