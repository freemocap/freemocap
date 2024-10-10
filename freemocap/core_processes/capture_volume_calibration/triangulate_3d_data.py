import logging
import multiprocessing
from pathlib import Path

import numpy as np

from freemocap.core_processes.capture_volume_calibration.anipose_camera_calibration.freemocap_anipose import CameraGroup
from freemocap.core_processes.capture_volume_calibration.save_3d_data_to_npy import (
    save_3d_data_to_npy,
)

logger = logging.getLogger(__name__)


def triangulate_3d_data(
    anipose_calibration_object: CameraGroup,
    image_2d_data: np.ndarray,
    use_triangulate_ransac: bool = False,
    kill_event: multiprocessing.Event = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    number_of_cameras = image_2d_data.shape[0]
    number_of_frames = image_2d_data.shape[1]
    number_of_tracked_points = image_2d_data.shape[2]
    number_of_spatial_dimensions = image_2d_data.shape[3]

    if not number_of_spatial_dimensions == 2:
        logger.error(
            f"This is supposed to be 2D data but, number_of_spatial_dimensions: {number_of_spatial_dimensions}"
        )
        raise ValueError

    # reshape data to collapse across 'frames' so it becomes [number_of_cameras,
    # number_of_2d_points(numFrames*numPoints), XY]
    data2d_flat = image_2d_data.reshape(number_of_cameras, -1, 2)

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

    spatial_data3d_numFrames_numTrackedPoints_XYZ = data3d_flat.reshape(number_of_frames, number_of_tracked_points, 3)

    data3d_reprojectionError_flat = anipose_calibration_object.reprojection_error(data3d_flat, data2d_flat, mean=True)
    data3d_reprojectionError_full = anipose_calibration_object.reprojection_error(data3d_flat, data2d_flat, mean=False)
    reprojectionError_cam_frame_marker = np.linalg.norm(data3d_reprojectionError_full, axis=2).reshape(
        number_of_cameras, number_of_frames, number_of_tracked_points
    )

    reprojection_error_data3d_numFrames_numTrackedPoints = data3d_reprojectionError_flat.reshape(
        number_of_frames, number_of_tracked_points
    )

    return (
        spatial_data3d_numFrames_numTrackedPoints_XYZ,
        reprojection_error_data3d_numFrames_numTrackedPoints,
        reprojectionError_cam_frame_marker,
    )


if __name__ == "__main__":
    from freemocap.core_processes.capture_volume_calibration.anipose_camera_calibration.get_anipose_calibration_object import (
        load_anipose_calibration_toml_from_path,
    )
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data_2d_path",
        type=str,
        help="path to 2d data",
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
    parser.add_argument(
        "--file_prefix",
        type=str,
        help="file prefix",
        required=False,
    )
    args = parser.parse_args()

    data_2d = np.load(args.data_2d_path)

    if args.output_data_folder_path is None:
        args.output_data_folder_path = Path(args.data_2d_path).parent

    if args.save_data_as_csv is None:
        args.save_data_as_csv = True  # default

    if args.use_triangulate_ransac is None:
        args.use_triangulate_ransac = True

    if args.file_prefix is None:
        args.file_prefix = ""

    if args.calibration_file_path:
        anipose_calibration_object = load_anipose_calibration_toml_from_path(args.calibration_file_path)
    else:
        anipose_calibration_object = load_anipose_calibration_toml_from_path(
            Path(args.data_2d_path).parent.parent / "camera_calibration_data.toml"
        )

    (
        skel3d_frame_marker_xyz,
        skeleton_reprojection_error_fr_mar,
        skeleton_reprojection_error_cam_fr_mar,
    ) = triangulate_3d_data(
        anipose_calibration_object=anipose_calibration_object,
        image_2d_data=data_2d,
        use_triangulate_ransac=args.use_triangulate_ransac,
    )
    save_3d_data_to_npy(
        data3d_numFrames_numTrackedPoints_XYZ=skel3d_frame_marker_xyz,
        data3d_numFrames_numTrackedPoints_reprojectionError=skeleton_reprojection_error_fr_mar,
        data3d_numCams_numFrames_numTrackedPoints_reprojectionError=skeleton_reprojection_error_cam_fr_mar,
        path_to_folder_where_data_will_be_saved=args.output_data_folder_path,
        processing_level="raw",
        file_prefix=args.file_prefix,
    )
