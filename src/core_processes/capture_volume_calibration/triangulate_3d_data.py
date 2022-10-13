from pathlib import Path
from typing import Union

import numpy as np
import logging

import toml

from src.core_processes.mediapipe_stuff.convert_mediapipe_npy_to_csv import (
    convert_mediapipe_npy_to_csv,
)

logger = logging.getLogger(__name__)


def threshold_by_confidence(
    mediapipe_2d_data: np.ndarray,
    mediapipe_confidence_cutoff_threshold: float = 0.0,
):
    mediapipe_2d_data[
        mediapipe_2d_data <= mediapipe_confidence_cutoff_threshold
    ] = np.NaN

    number_of_nans = np.sum(np.isnan(mediapipe_2d_data))
    number_of_points = np.prod(mediapipe_2d_data.shape)
    percentage_that_are_nans = (
        np.sum(np.isnan(mediapipe_2d_data)) / number_of_points
    ) * 100
    logger.info(
        f"After thresholding `mediapipe_2d` with a confidence threshold {mediapipe_confidence_cutoff_threshold}, it has {number_of_nans} NaN values out of {number_of_points} ({percentage_that_are_nans} %)"
    )
    return mediapipe_2d_data


def triangulate_3d_data(
    anipose_calibration_object,
    mediapipe_2d_data: np.ndarray,
    output_data_folder_path: Union[str, Path],
    mediapipe_confidence_cutoff_threshold: float,
    save_data_as_csv: bool,
    use_triangulate_ransac: bool = True,
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

    mediapipe_2d_data = threshold_by_confidence(
        mediapipe_2d_data=mediapipe_2d_data,
        mediapipe_confidence_cutoff_threshold=mediapipe_confidence_cutoff_threshold,
    )

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

    if use_triangulate_ransac:
        logger.info("Using `triangulate_ransac` method (slower, but more accurate)")
        data3d_flat = anipose_calibration_object.triangulate_ransac(
            data2d_flat, progress=True
        )
    else:
        logger.info("Using `triangulate` method (faster, but less accurate)")
        data3d_flat = anipose_calibration_object.triangulate(data2d_flat, progress=True)

    data3d_reprojectionError_flat = anipose_calibration_object.reprojection_error(
        data3d_flat, data2d_flat, mean=False
    )

    spatial_data3d_numFrames_numTrackedPoints_XYZ = data3d_flat.reshape(
        number_of_frames, number_of_tracked_points, 3
    )
    reprojection_error_data3d_numCams_numFrames_numTrackedPoints_error = (
        data3d_reprojectionError_flat.reshape(
            number_of_cameras, number_of_frames, number_of_tracked_points, 2
        )
    )

    save_mediapipe_3d_data_to_npy(
        data3d_numFrames_numTrackedPoints_XYZ=spatial_data3d_numFrames_numTrackedPoints_XYZ,
        data3d_numFrames_numTrackedPoints_reprojectionError=reprojection_error_data3d_numCams_numFrames_numTrackedPoints_error,
        output_data_folder_path=output_data_folder_path,
    )

    if save_data_as_csv:
        convert_mediapipe_npy_to_csv(
            spatial_data3d_numFrames_numTrackedPoints_XYZ, output_data_folder_path
        )


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


if __name__ == "__main__":
    import argparse
    from src.core_processes.capture_volume_calibration.get_anipose_calibration_object import (
        load_anipose_calibration_toml_from_path,
    )

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mediapipe_2d_data_path",
        type=str,
        help="path to mediapipe 2d data",
        required=True,
    )
    parser.add_argument(
        "--output_data_folder_path",
        type=str,
        help="path to output folder",
        required=False,
    )
    parser.add_argument(
        "--calibration_file_path",
        type=str,
        help="path to calibration file",
        required=False,
    )
    parser.add_argument(
        "--mediapipe_confidence_cutoff_threshold",
        type=float,
        help="confidence cutoff threshold",
        required=False,
    )
    parser.add_argument(
        "--save_data_as_csv",
        type=bool,
        help="save data as csv",
        required=False,
    )
    parser.add_argument(
        "--use_triangulate_ransac",
        type=bool,
        help="use triangulate ransac anipose method ",
        required=False,
    )
    args = parser.parse_args()

    mediapipe_2d_data = np.load(args.mediapipe_2d_data_path)

    if args.mediapipe_confidence_cutoff_threshold is None:
        args.mediapipe_confidence_cutoff_threshold = 0.7  # default

    if args.output_data_folder_path is None:
        args.output_data_folder_path = Path(args.mediapipe_2d_data_path).parent

    if args.save_data_as_csv is None:
        args.save_data_as_csv = True  # default

    if args.use_triangulate_ransac is None:
        args.use_triangulate_ransac = False

    if args.calibration_file_path:
        anipose_calibration_object = load_anipose_calibration_toml_from_path(
            args.calibration_file_path
        )
    else:
        anipose_calibration_object = load_anipose_calibration_toml_from_path(
            Path(args.mediapipe_2d_data_path).parent.parent
            / "camera_calibration_data.toml"
        )

    triangulate_3d_data(
        anipose_calibration_object=anipose_calibration_object,
        mediapipe_2d_data=mediapipe_2d_data,
        output_data_folder_path=args.output_data_folder_path,
        mediapipe_confidence_cutoff_threshold=args.mediapipe_confidence_cutoff_threshold,
        save_data_as_csv=args.save_data_as_csv,
        use_triangulate_ransac=args.use_triangulate_ransac,
    )
