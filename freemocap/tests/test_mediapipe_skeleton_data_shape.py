from pathlib import Path
from typing import Union

import numpy as np
import pytest

from freemocap.utilities.get_number_of_frames_of_videos_in_a_folder import (
    get_number_of_frames_of_videos_in_a_folder,
)


@pytest.mark.usefixtures("synchronized_video_folder_path", "raw_skeleton_npy_file_path", "reprojection_error_file_path")
def test_mediapipe_skeleton_data_shape(
    synchronized_video_folder_path: Union[str, Path],
    raw_skeleton_npy_file_path: Union[str, Path],
    reprojection_error_file_path,
):
    """
    test that the `mediapipe 3d detection` process worked correctly by checking:

    1. There is an `.npy` file containing the mediapipe 3d data in the `output_data_folder`
    2. The dimensions of that `npy` ( number of frames, [ need to do - number of tracked points], [X,Y,Z] matches the videos in the `synchronized videos` folder

    TODO - check number of tracked points vs 'expected' number of tracked points
    """

    assert Path(
        raw_skeleton_npy_file_path
    ).is_file(), f"3d skeleton data file does not exist at {raw_skeleton_npy_file_path}"

    skel3d_frame_marker_xyz = np.load(raw_skeleton_npy_file_path)

    assert (
        len(skel3d_frame_marker_xyz.shape) == 3
    ), f"3d skeleton data file should have 3 dimensions -  {raw_skeleton_npy_file_path}"

    assert Path(
        reprojection_error_file_path
    ).is_file(), f"3d skeleton reprojection error data file does not exist at {reprojection_error_file_path}"

    skeleton_reprojection_error_fr_mar = np.load(reprojection_error_file_path)

    assert (
        len(skeleton_reprojection_error_fr_mar.shape) == 2
    ), f"3d skeleton reprojection error data file should have 2 dimensions {reprojection_error_file_path}"

    frame_count = get_number_of_frames_of_videos_in_a_folder(synchronized_video_folder_path)
    assert (
        len(set(frame_count)) == 1
    ), f"Videos in {synchronized_video_folder_path} have different frame counts: {frame_count}"

    number_of_frames = frame_count[0]

    assert skel3d_frame_marker_xyz.shape[0] == number_of_frames
    assert skeleton_reprojection_error_fr_mar.shape[0] == number_of_frames

    # TODO - check number of tracked points vs 'expected' number of tracked points

    assert (
        skel3d_frame_marker_xyz.shape[2] == 3
    ), f"3d skeleton data file does not have 3 dimensions for X,Y,Z at {raw_skeleton_npy_file_path}"
