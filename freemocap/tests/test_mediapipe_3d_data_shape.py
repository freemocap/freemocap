from pathlib import Path
from typing import Union

import numpy as np

from freemocap.tests.utilities.get_number_of_frames_of_videos_in_a_folder import (
    get_number_of_frames_of_videos_in_a_folder,
)


def test_mediapipe_3d_data_shape(
    synchronized_videos_folder: Union[str, Path],
    mediapipe_3d_data_npy_path: Union[str, Path],
    medipipe_reprojection_error_data_npy_path: Union[str, Path],
):
    """
    test that the `mediapipe 3d detection` process worked correctly by checking:

    1. There is an `.npy` file containing the mediapipe 3d data in the `output_data_folder`
    2. The dimensions of that `npy` ( number of frames, [ need to do - number of tracked points], [X,Y,Z] matches the videos in the `synchronized videos` folder

    TODO - check number of tracked points vs 'expected' number of tracked points
    """

    assert Path(
        mediapipe_3d_data_npy_path
    ).is_file(), f"3d skeleton data file does not exist at {mediapipe_3d_data_npy_path}"

    skel3d_frame_marker_xyz = np.load(mediapipe_3d_data_npy_path)

    assert (
        len(skel3d_frame_marker_xyz.shape) == 3
    ), f"3d skeleton data file should have 3 dimensions -  {mediapipe_3d_data_npy_path}"

    assert Path(
        medipipe_reprojection_error_data_npy_path
    ).is_file(), f"3d skeleton reprojection error data file does not exist at {medipipe_reprojection_error_data_npy_path}"

    skeleton_reprojection_error_fr_mar = np.load(
        medipipe_reprojection_error_data_npy_path
    )

    assert (
        len(skeleton_reprojection_error_fr_mar.shape) == 2
    ), f"3d skeleton reprojection error data file should have 2 dimensions {medipipe_reprojection_error_data_npy_path}"

    frame_count = get_number_of_frames_of_videos_in_a_folder(synchronized_videos_folder)
    assert (
        len(set(frame_count)) == 1
    ), f"Videos in {synchronized_videos_folder} have different frame counts: {frame_count}"

    number_of_frames = frame_count[0]

    assert skel3d_frame_marker_xyz.shape[0] == number_of_frames
    assert skeleton_reprojection_error_fr_mar.shape[0] == number_of_frames

    # TODO - check number of tracked points vs 'expected' number of tracked points

    assert (
        skel3d_frame_marker_xyz.shape[2] == 3
    ), f"3d skeleton data file does not have 3 dimensions for X,Y,Z at {mediapipe_3d_data_npy_path}"

    return True
