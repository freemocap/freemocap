import logging
from pathlib import Path
from typing import Union

import numpy as np

from freemocap.system.paths_and_filenames.file_and_folder_names import (
    RAW_MEDIAPIPE_3D_NPY_FILE_NAME,
    RAW_MEDIAPIPE_REPROJECTION_ERROR_NPY_FILE_NAME,
    REPROJECTION_FILTERED_MEDIAPIPE_3D_NPY_FILE_NAME,
    REPROJECTION_FILTERED_MEDIAPIPE_REPROJECTION_ERROR_NPY_FILE_NAME,
)

logger = logging.getLogger(__name__)


def save_mediapipe_3d_data_to_npy(
    data3d_numFrames_numTrackedPoints_XYZ: np.ndarray,
    data3d_numFrames_numTrackedPoints_reprojectionError: np.ndarray,
    path_to_folder_where_data_will_be_saved: Union[str, Path],
    processing_level: str,
):
    path_to_folder_where_data_will_be_saved = Path(path_to_folder_where_data_will_be_saved)
    Path(path_to_folder_where_data_will_be_saved).mkdir(parents=True, exist_ok=True)  # save spatial XYZ data
    if processing_level == "raw":
        mediapipe_3dData_save_path = path_to_folder_where_data_will_be_saved / RAW_MEDIAPIPE_3D_NPY_FILE_NAME
        mediapipe_reprojection_error_save_path = (
            path_to_folder_where_data_will_be_saved / RAW_MEDIAPIPE_REPROJECTION_ERROR_NPY_FILE_NAME
        )
    elif processing_level == "reprojection_filtered":
        mediapipe_3dData_save_path = (
            path_to_folder_where_data_will_be_saved / REPROJECTION_FILTERED_MEDIAPIPE_3D_NPY_FILE_NAME
        )
        mediapipe_reprojection_error_save_path = (
            path_to_folder_where_data_will_be_saved / REPROJECTION_FILTERED_MEDIAPIPE_REPROJECTION_ERROR_NPY_FILE_NAME
        )
    else:
        logger.exception(f"processing_level: {processing_level} not recognized")
        raise Exception

    logger.info(f"saving: {mediapipe_3dData_save_path}")
    np.save(str(mediapipe_3dData_save_path), data3d_numFrames_numTrackedPoints_XYZ)

    # save reprojection error

    logger.info(f"saving: {mediapipe_reprojection_error_save_path}")
    np.save(
        str(mediapipe_reprojection_error_save_path),
        data3d_numFrames_numTrackedPoints_reprojectionError,
    )
