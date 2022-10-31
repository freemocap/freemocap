from pathlib import Path
from typing import Union

import cv2
import numpy as np

from src.config.home_dir import (
    MEDIAPIPE_3D_NPY_FILE_NAME,
    MEDIAPIPE_REPROJECTION_ERROR_NPY_FILE_NAME,
    MEDIAPIPE_2D_NPY_FILE_NAME,
)


def test_mediapipe_2d_data(
    synchronized_videos_folder: Union[str, Path],
    output_data_folder: Union[str, Path],
    mediapipe_2d_data: np.ndarray,
):

    """
    test that the `mediapipe 2d detection` process worked correctly by checking:

    1. There is an `.npy` file containing the mediapipe 2d data in the `output_data_folder`
    2. The dimensions of that `npy` (number of cameras, number of frames, [ need to do - number of tracked points], [pixelX, pixelY] matches the videos in the `synchronized videos` folder

    TODO - check number of tracked points vs 'expected' number of tracked points
    """

    mediapipe_2d_data_file_path = output_data_folder / MEDIAPIPE_2D_NPY_FILE_NAME
    assert mediapipe_2d_data_file_path.exists()

    saved_mediapipe_2d_data = np.load(mediapipe_2d_data_file_path)
    assert np.array_equal(saved_mediapipe_2d_data, mediapipe_2d_data, equal_nan=True)

    list_of_video_paths = list(synchronized_videos_folder.glob("*.mp4"))
    number_of_videos = len(list_of_video_paths)
    assert mediapipe_2d_data.shape[0] == number_of_videos

    video_0_cv2_capture_object = cv2.VideoCapture(str(list_of_video_paths[0]))

    number_of_frames_in_video_0 = int(
        video_0_cv2_capture_object.get(cv2.CAP_PROP_FRAME_COUNT)
    )
    assert mediapipe_2d_data.shape[1] == number_of_frames_in_video_0

    # TODO - check number of tracked points vs 'expected' number of tracked points

    assert mediapipe_2d_data.shape[3] == 2

    return True


def test_mediapipe_3d_data(
    synchronized_videos_folder: Union[str, Path],
    output_data_folder: Union[str, Path],
    skel3d_frame_marker_xyz: np.ndarray,
    skeleton_reprojection_error_fr_mar: np.ndarray,
):
    """
    test that the `mediapipe 3d detection` process worked correctly by checking:

    1. There is an `.npy` file containing the mediapipe 3d data in the `output_data_folder`
    2. The dimensions of that `npy` ( number of frames, [ need to do - number of tracked points], [X,Y,Z] matches the videos in the `synchronized videos` folder

    TODO - check number of tracked points vs 'expected' number of tracked points
    """

    mediapipe_3d_spatial_data_file_path = (
        output_data_folder / MEDIAPIPE_3D_NPY_FILE_NAME
    )
    assert mediapipe_3d_spatial_data_file_path.exists()

    saved_spatial_data = np.load(mediapipe_3d_spatial_data_file_path)
    assert np.array_equal(saved_spatial_data, skel3d_frame_marker_xyz, equal_nan=True)

    mediapipe_reprojection_error_file_path = (
        output_data_folder / MEDIAPIPE_REPROJECTION_ERROR_NPY_FILE_NAME
    )
    assert mediapipe_reprojection_error_file_path.exists()

    saved_reprojection_error = np.load(mediapipe_reprojection_error_file_path)
    assert np.array_equal(
        saved_reprojection_error, skeleton_reprojection_error_fr_mar, equal_nan=True
    )

    list_of_video_paths = list(synchronized_videos_folder.glob("*.mp4"))

    video_0_cv2_capture_object = cv2.VideoCapture(str(list_of_video_paths[0]))

    number_of_frames_in_video_0 = int(
        video_0_cv2_capture_object.get(cv2.CAP_PROP_FRAME_COUNT)
    )
    assert skel3d_frame_marker_xyz.shape[0] == number_of_frames_in_video_0
    assert skeleton_reprojection_error_fr_mar.shape[0] == number_of_frames_in_video_0

    # TODO - check number of tracked points vs 'expected' number of tracked points

    assert skel3d_frame_marker_xyz.shape[2] == 3

    return True
