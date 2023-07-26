import logging
import multiprocessing
from pathlib import Path
from typing import Union

import numpy as np

from freemocap.system.paths_and_filenames.file_and_folder_names import (
    RAW_MEDIAPIPE_3D_NPY_FILE_NAME,
    MEDIAPIPE_REPROJECTION_ERROR_NPY_FILE_NAME,
)

logger = logging.getLogger(__name__)


def threshold_by_confidence(
    mediapipe_2d_data: np.ndarray,
    mediapipe_confidence_cutoff_threshold: float = 0.0,
):
    mediapipe_2d_data[mediapipe_2d_data <= mediapipe_confidence_cutoff_threshold] = np.NaN

    number_of_nans = np.sum(np.isnan(mediapipe_2d_data))
    number_of_points = np.prod(mediapipe_2d_data.shape)
    percentage_that_are_nans = (np.sum(np.isnan(mediapipe_2d_data)) / number_of_points) * 100
    logger.info(
        f"After thresholding `mediapipe_2d` with a confidence threshold {mediapipe_confidence_cutoff_threshold}, it has {number_of_nans} NaN values out of {number_of_points} ({percentage_that_are_nans} %)"
    )
    return mediapipe_2d_data


def remove_3d_data_with_high_reprojection_error(
    data3d_numFrames_numTrackedPoints_XYZ: np.ndarray,
    data3d_numFrames_numTrackedPoints_reprojectionError: np.ndarray,
):
    return data3d_numFrames_numTrackedPoints_XYZ
    # TODO - Fix this function (it was causing overfiltering when combined with the anipose calibration confidence thresholding)

    logger.info("Removing 3D data with high reprojection error")
    mean_reprojection_error_per_frame = np.nanmean(
        data3d_numFrames_numTrackedPoints_reprojectionError,
        axis=1,
    )

    reprojection_error_mean = np.nanmean(mean_reprojection_error_per_frame)
    reprojection_error_median = np.nanmedian(mean_reprojection_error_per_frame)
    reprojection_error_std = np.nanstd(mean_reprojection_error_per_frame)

    median_absolute_deviation = np.nanmedian(np.abs(mean_reprojection_error_per_frame - reprojection_error_median))

    logger.info(
        f"\nInitial reprojection error - \nmean: {reprojection_error_mean:.3f},\nstandard deviation: {reprojection_error_std:.3f},\nmedian: {reprojection_error_median}\nmedian absolute deviation: {median_absolute_deviation:.3f}"
    )

    error_threshold = reprojection_error_median + 3 * median_absolute_deviation

    number_of_nans_before_thresholding = np.sum(np.isnan(data3d_numFrames_numTrackedPoints_XYZ))

    # replace points with high reprojection error with `np.nan`
    data3d_numFrames_numTrackedPoints_XYZ[
        data3d_numFrames_numTrackedPoints_reprojectionError > error_threshold
    ] = np.nan

    number_of_nans_after_thresholding = np.sum(np.isnan(data3d_numFrames_numTrackedPoints_XYZ))
    percentage_of_nans_removed = (
        (number_of_nans_before_thresholding - number_of_nans_after_thresholding)
        / number_of_nans_before_thresholding
        * 100
    )

    logger.info(f"Removing points with reprojection error > {error_threshold:.3f}")
    logger.info(f"Number of NaNs before thresholding: {number_of_nans_before_thresholding}")
    logger.info(
        f"Number of NaNs after thresholding: {number_of_nans_after_thresholding} ({percentage_of_nans_removed:.2f} %)"
    )

    return data3d_numFrames_numTrackedPoints_XYZ


def triangulate_3d_data(
    anipose_calibration_object,
    mediapipe_2d_data: np.ndarray,
    output_data_folder_path: Union[str, Path],
    mediapipe_confidence_cutoff_threshold: float,
    use_triangulate_ransac: bool = False,
    kill_event: multiprocessing.Event = None,
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

    # mediapipe_2d_data = threshold_by_confidence(
    #     mediapipe_2d_data=mediapipe_2d_data,
    #     mediapipe_confidence_cutoff_threshold=mediapipe_confidence_cutoff_threshold,
    # )

    # reshape data to collapse across 'frames' so it becomes [number_of_cameras,
    # number_of_2d_points(numFrames*numPoints), XY]
    data2d_flat = mediapipe_2d_data.reshape(number_of_cameras, -1, 2)

    logger.info(
        f"Reconstructing 3d points from 2d points with shape: \n"
        f"number_of_cameras: {number_of_cameras},\n"
        f"number_of_frames: {number_of_frames}, \n"
        f"number_of_tracked_points: {number_of_tracked_points},\n"
        f"number_of_spatial_dimensions: {number_of_spatial_dimensions}"
    )

    if use_triangulate_ransac:
        logger.info("Using `triangulate_ransac` method")
        data3d_flat = anipose_calibration_object.triangulate_ransac(data2d_flat, progress=True, kill_event=kill_event)
    else:
        logger.info("Using simple `triangulate` method ")
        data3d_flat = anipose_calibration_object.triangulate(data2d_flat, progress=True, kill_event=kill_event)

    spatial_data3d_numFrames_numTrackedPoints_XYZ_og = data3d_flat.reshape(
        number_of_frames, number_of_tracked_points, 3
    )

    data3d_reprojectionError_flat = anipose_calibration_object.reprojection_error(data3d_flat, data2d_flat, mean=True)

    reprojection_error_data3d_numFrames_numTrackedPoints = data3d_reprojectionError_flat.reshape(
        number_of_frames, number_of_tracked_points
    )

    spatial_data3d_numFrames_numTrackedPoints_XYZ = remove_3d_data_with_high_reprojection_error(
        data3d_numFrames_numTrackedPoints_XYZ=spatial_data3d_numFrames_numTrackedPoints_XYZ_og,
        data3d_numFrames_numTrackedPoints_reprojectionError=reprojection_error_data3d_numFrames_numTrackedPoints,
    )

    save_mediapipe_3d_data_to_npy(
        data3d_numFrames_numTrackedPoints_XYZ=spatial_data3d_numFrames_numTrackedPoints_XYZ,
        data3d_numFrames_numTrackedPoints_reprojectionError=reprojection_error_data3d_numFrames_numTrackedPoints,
        path_to_folder_where_data_will_be_saved=output_data_folder_path,
    )
    # TODO - don't output multiple variables, make this a dataclass/BAG pattern or something
    return (
        spatial_data3d_numFrames_numTrackedPoints_XYZ,
        reprojection_error_data3d_numFrames_numTrackedPoints,
    )


def save_mediapipe_3d_data_to_npy(
    data3d_numFrames_numTrackedPoints_XYZ: np.ndarray,
    data3d_numFrames_numTrackedPoints_reprojectionError: np.ndarray,
    path_to_folder_where_data_will_be_saved: Union[str, Path],
):
    path_to_folder_where_data_will_be_saved = Path(path_to_folder_where_data_will_be_saved)
    Path(path_to_folder_where_data_will_be_saved).mkdir(parents=True, exist_ok=True)  # save spatial XYZ data
    mediapipe_3dData_save_path = path_to_folder_where_data_will_be_saved / RAW_MEDIAPIPE_3D_NPY_FILE_NAME

    logger.info(f"saving: {mediapipe_3dData_save_path}")
    np.save(str(mediapipe_3dData_save_path), data3d_numFrames_numTrackedPoints_XYZ)

    # save reprojection error
    mediapipe_reprojection_error_save_path = (
        path_to_folder_where_data_will_be_saved / MEDIAPIPE_REPROJECTION_ERROR_NPY_FILE_NAME
    )

    logger.info(f"saving: {mediapipe_reprojection_error_save_path}")
    np.save(
        str(mediapipe_reprojection_error_save_path),
        data3d_numFrames_numTrackedPoints_reprojectionError,
    )


if __name__ == "__main__":
    from freemocap.core_processes.capture_volume_calibration.anipose_camera_calibration.get_anipose_calibration_object import (
        load_anipose_calibration_toml_from_path,
    )
    import argparse

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
        args.use_triangulate_ransac = True

    if args.calibration_file_path:
        anipose_calibration_object = load_anipose_calibration_toml_from_path(args.calibration_file_path)
    else:
        anipose_calibration_object = load_anipose_calibration_toml_from_path(
            Path(args.mediapipe_2d_data_path).parent.parent / "camera_calibration_data.toml"
        )

    triangulate_3d_data(
        anipose_calibration_object=anipose_calibration_object,
        mediapipe_2d_data=mediapipe_2d_data,
        output_data_folder_path=args.output_data_folder_path,
        mediapipe_confidence_cutoff_threshold=args.mediapipe_confidence_cutoff_threshold,
        use_triangulate_ransac=args.use_triangulate_ransac,
    )
