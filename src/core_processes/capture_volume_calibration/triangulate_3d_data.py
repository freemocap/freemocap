from pathlib import Path
from typing import Union

import numpy as np
import logging

logger = logging.getLogger(__name__)


def triangulate_3d_data(
    anipose_calibration_object,
    mediapipe_2d_data: np.ndarray,
    output_data_folder_path: Union[str, Path],
):
    number_of_cameras = mediapipe_2d_data.shape[0]
    number_of_frames = mediapipe_2d_data.shape[1]
    number_of_tracked_points = mediapipe_2d_data.shape[2]
    number_of_spatial_dimensions = mediapipe_2d_data.shape[3]

    if not number_of_spatial_dimensions == 2:
        logger.error(
            f"This is supposed to be 2D data but, number_of_spatial_dimensions: {number_of_spatial_dimensions}"
        )
        raise Exception

    # reshape data to collapse across 'frames' so it becomes [number_of_cameras,
    # number_of_2d_points(numFrames*numPoints), XY]
    data2d_flat = mediapipe_2d_data.reshape(number_of_cameras, -1, 2)

    logger.info(
        f"Reconstructing 3d points from 2d points with shape: "
        f"number_of_cameras: {number_of_cameras},"
        f" number_of_frames: {number_of_frames}, "
        f" number_of_tracked_points: {number_of_tracked_points},"
        f" number_of_spatial_dimensions: {number_of_spatial_dimensions}"
    )

    data3d_flat = anipose_calibration_object.triangulate(data2d_flat, progress=True)

    data3d_reprojectionError_flat = anipose_calibration_object.reprojection_error(
        data3d_flat, data2d_flat, mean=True
    )

    data3d_numFrames_numTrackedPoints_XYZ = data3d_flat.reshape(
        number_of_frames, number_of_tracked_points, 3
    )
    data3d_numFrames_numTrackedPoints_reprojectionError = (
        data3d_reprojectionError_flat.reshape(
            number_of_frames, number_of_tracked_points
        )
    )

    path_to_3d_data_npy = save_mediapipe_3d_data_to_npy(
        data3d_numFrames_numTrackedPoints_XYZ=data3d_numFrames_numTrackedPoints_XYZ,
        data3d_numFrames_numTrackedPoints_reprojectionError=data3d_numFrames_numTrackedPoints_reprojectionError,
        output_data_folder_path=output_data_folder_path,
    )

    return path_to_3d_data_npy


def save_mediapipe_3d_data_to_npy(
    data3d_numFrames_numTrackedPoints_XYZ: np.ndarray,
    data3d_numFrames_numTrackedPoints_reprojectionError: np.ndarray,
    output_data_folder_path: Union[str, Path],
):
    # save spatial XYZ data
    mediapipe_3dData_save_path = (
        Path(output_data_folder_path)
        / "mediapipe_3dData_numFrames_numTrackedPoints_spatialXYZ.npy"
    )

    logger.info(f"saving: {mediapipe_3dData_save_path}")
    np.save(str(mediapipe_3dData_save_path), data3d_numFrames_numTrackedPoints_XYZ)

    # save reprojection error
    mediapipe_reprojection_error_save_path = (
        Path(output_data_folder_path)
        / "mediapipe_3dData_numFrames_numTrackedPoints_reprojectionError.npy"
    )

    logger.info(f"saving: {mediapipe_reprojection_error_save_path}")
    np.save(
        str(mediapipe_reprojection_error_save_path),
        data3d_numFrames_numTrackedPoints_reprojectionError,
    )
