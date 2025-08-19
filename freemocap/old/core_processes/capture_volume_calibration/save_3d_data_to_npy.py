import logging
from pathlib import Path
from typing import Union

import numpy as np

from freemocap.system.paths_and_filenames.file_and_folder_names import (
    RAW_3D_NPY_FILE_NAME,
    FULL_REPROJECTION_ERROR_NPY_FILE_NAME,
    REPROJECTION_ERROR_NPY_FILE_NAME,
    REPROJECTION_FILTERED_PREFIX,
)

logger = logging.getLogger(__name__)


def save_3d_data_to_npy(
    data3d_numFrames_numTrackedPoints_XYZ: np.ndarray,
    data3d_numFrames_numTrackedPoints_reprojectionError: np.ndarray,
    data3d_numCams_numFrames_numTrackedPoints_reprojectionError: np.ndarray,
    path_to_folder_where_data_will_be_saved: Union[str, Path],
    processing_level: str,
    file_prefix: str = "",
):
    path_to_folder_where_data_will_be_saved = Path(path_to_folder_where_data_will_be_saved)
    Path(path_to_folder_where_data_will_be_saved).mkdir(parents=True, exist_ok=True)  # save spatial XYZ data
    if processing_level == "raw":
        data_3d_save_path = path_to_folder_where_data_will_be_saved / f"{file_prefix}_{RAW_3D_NPY_FILE_NAME}"
        reprojection_error_save_path = (
            path_to_folder_where_data_will_be_saved / f"{file_prefix}_{REPROJECTION_ERROR_NPY_FILE_NAME}"
        )
        full_reprojection_error_save_path = (
            path_to_folder_where_data_will_be_saved / f"{file_prefix}_{FULL_REPROJECTION_ERROR_NPY_FILE_NAME}"
        )
    elif processing_level == "reprojection_filtered":
        data_3d_save_path = (
            path_to_folder_where_data_will_be_saved
            / f"{REPROJECTION_FILTERED_PREFIX}{file_prefix}_{RAW_3D_NPY_FILE_NAME}"
        )
        reprojection_error_save_path = (
            path_to_folder_where_data_will_be_saved
            / f"{REPROJECTION_FILTERED_PREFIX}{file_prefix}_{REPROJECTION_ERROR_NPY_FILE_NAME}"
        )
        full_reprojection_error_save_path = (
            path_to_folder_where_data_will_be_saved
            / f"{REPROJECTION_FILTERED_PREFIX}{file_prefix}_{FULL_REPROJECTION_ERROR_NPY_FILE_NAME}"
        )
    else:
        logger.exception(f"processing_level: {processing_level} not recognized")
        raise Exception

    logger.info(f"saving: {data_3d_save_path}")
    np.save(str(data_3d_save_path), data3d_numFrames_numTrackedPoints_XYZ)

    # save reprojection error

    logger.info(f"saving: {reprojection_error_save_path}")
    np.save(
        str(reprojection_error_save_path),
        data3d_numFrames_numTrackedPoints_reprojectionError,
    )

    logger.info(f"saving: {full_reprojection_error_save_path}")
    np.save(
        str(full_reprojection_error_save_path),
        data3d_numCams_numFrames_numTrackedPoints_reprojectionError,
    )
