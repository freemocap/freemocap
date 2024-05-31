from pathlib import Path
from typing import Optional, Union

import numpy as np
import pytest

from freemocap.utilities.get_number_of_frames_of_videos_in_a_folder import (
    get_number_of_frames_of_videos_in_a_folder,
)


@pytest.mark.usefixtures("raw_skeleton_npy_file_path", "reprojection_error_file_path")
def test_skeleton_data_exists(
    raw_skeleton_npy_file_path: Union[str, Path],
    reprojection_error_file_path: Union[str, Path],
):
    """
    test that the `3d detection` process worked correctly by checking that there is an `.npy` file containing the 3d data in the `output_data_folder`
    """

    assert Path(
        raw_skeleton_npy_file_path
    ).is_file(), f"3d skeleton data file does not exist at {raw_skeleton_npy_file_path}"

    assert Path(
        reprojection_error_file_path
    ).is_file(), f"3d skeleton reprojection error data file does not exist at {reprojection_error_file_path}"


@pytest.mark.usefixtures("synchronized_video_folder_path", "raw_skeleton_npy_file_path", "reprojection_error_file_path")
def test_skeleton_data_shape(
    synchronized_video_folder_path: Union[str, Path],
    raw_skeleton_npy_file_path: Optional[Union[str, Path]] = None,
    reprojection_error_file_path: Optional[Union[str, Path]] = None,
    raw_skeleton_npy: Optional[np.ndarray] = None,
    reprojection_error_npy: Optional[np.ndarray] = None,
):
    """
    test that the `3d detection` process worked correctly by checking:
    1. Dimensions of the raw skeleton numpy array are correct
    2. Dimensions of the reprojection error numpy array are correct
    """
    if raw_skeleton_npy is None and raw_skeleton_npy_file_path is None:
        raise ValueError("Must provide either raw_skeleton_npy or raw_skeleton_npy_file_path")
    elif raw_skeleton_npy is None:
        skel3d_frame_marker_xyz = np.load(raw_skeleton_npy_file_path)
    else:
        skel3d_frame_marker_xyz = raw_skeleton_npy

    assert (
        len(skel3d_frame_marker_xyz.shape) == 3
    ), f"3d skeleton data file should have 3 dimensions -  {raw_skeleton_npy_file_path}"

    if reprojection_error_npy is None and reprojection_error_file_path is None:
        raise ValueError("Must provide either raw_skeleton_npy or raw_skeleton_npy_file_path")
    elif reprojection_error_npy is None:
        skeleton_reprojection_error_fr_mar = np.load(reprojection_error_file_path)
    else:
        skeleton_reprojection_error_fr_mar = reprojection_error_npy

    assert (
        len(skeleton_reprojection_error_fr_mar.shape) == 2
    ), f"3d skeleton reprojection error data file should have 2 dimensions {reprojection_error_file_path}"

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
    ), f"3d skeleton data file does not have 3 dimensions for X,Y,Z at {raw_skeleton_npy_file_path}"
