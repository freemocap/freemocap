from pathlib import Path
from typing import Union

import numpy as np
import pytest

from freemocap.utilities.get_number_of_frames_of_videos_in_a_folder import (
    get_number_of_frames_of_videos_in_a_folder,
)


@pytest.mark.usefixtures("raw_skeleton_data", "reprojection_error_data")
def test_skeleton_data_exists(
    raw_skeleton_data: Union[str, Path],
    reprojection_error_data: Union[str, Path],
):
    """
    test that the `3d detection` process worked correctly by checking that there is an `.npy` file containing the 3d data in the `output_data_folder`
    """

    assert Path(
        raw_skeleton_data
    ).is_file(), f"3d skeleton data file does not exist at {raw_skeleton_data}"

    assert Path(
        reprojection_error_data
    ).is_file(), f"3d skeleton reprojection error data file does not exist at {reprojection_error_data}"


@pytest.mark.usefixtures("synchronized_video_folder_path", "raw_skeleton_data", "reprojection_error_data")
def test_skeleton_data_shape(
    synchronized_video_folder_path: Union[str, Path],
    raw_skeleton_data: Union[str, Path, np.ndarray],
    reprojection_error_data: Union[str, Path, np.ndarray],
):
    """
    test that the `3d detection` process worked correctly by checking:
    1. Dimensions of the raw skeleton numpy array are correct
    2. Dimensions of the reprojection error numpy array are correct
    """
    if isinstance(raw_skeleton_data, (str, Path)):
        skel3d_frame_marker_xyz = np.load(raw_skeleton_data)
    else:
        skel3d_frame_marker_xyz = raw_skeleton_data

    assert (
        len(skel3d_frame_marker_xyz.shape) == 3
    ), f"3d skeleton data file should have 3 dimensions, but has shape  {skel3d_frame_marker_xyz.shape}"

    if isinstance(reprojection_error_data, (str, Path)):
        skeleton_reprojection_error_fr_mar = np.load(reprojection_error_data)
    else:
        skeleton_reprojection_error_fr_mar = reprojection_error_data

    assert (
        len(skeleton_reprojection_error_fr_mar.shape) == 2
    ), f"3d skeleton reprojection error data file should have 2 dimensions but has shape {skeleton_reprojection_error_fr_mar.shape}"

    frame_counts = list(get_number_of_frames_of_videos_in_a_folder(synchronized_video_folder_path).values())
    assert (
        len(set(frame_counts)) == 1
    ), f"Videos in {synchronized_video_folder_path} have different frame counts: {frame_counts}"

    number_of_frames = frame_counts[0]

    assert skel3d_frame_marker_xyz.shape[0] == number_of_frames
    assert skeleton_reprojection_error_fr_mar.shape[0] == number_of_frames

    # TODO - check number of tracked points vs 'expected' number of tracked points

    assert (
        skel3d_frame_marker_xyz.shape[2] == 3
    ), f"3d skeleton data file should have 3 dimensions for X,Y,Z, but instead has {skel3d_frame_marker_xyz.shape[2]}"
