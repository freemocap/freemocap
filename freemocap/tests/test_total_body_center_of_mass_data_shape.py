from pathlib import Path
from typing import Union

import numpy as np
import pytest

from freemocap.utilities.get_number_of_frames_of_videos_in_a_folder import (
    get_number_of_frames_of_videos_in_a_folder,
)


@pytest.mark.usefixtures("synchronized_video_folder_path", "total_body_center_of_mass_file_path")
def test_total_body_center_of_mass_data_shape(
    synchronized_video_folder_path: Union[str, Path],
    total_body_center_of_mass_file_path: Union[str, Path],
):
    assert Path(
        total_body_center_of_mass_file_path
    ).is_file(), f"No file found at {total_body_center_of_mass_file_path}"

    total_body_center_of_mass_fr_xyz = np.load(total_body_center_of_mass_file_path)

    frame_count = get_number_of_frames_of_videos_in_a_folder(synchronized_video_folder_path)
    assert (
        len(set(frame_count)) == 1
    ), f"Videos in {synchronized_video_folder_path} have different frame counts: {frame_count}"

    number_of_frames = frame_count[0]

    assert (
        total_body_center_of_mass_fr_xyz.shape[0] == number_of_frames
    ), f"Number of frames in {total_body_center_of_mass_file_path} does not match number of frames of videos in {synchronized_video_folder_path}"

    assert (
        total_body_center_of_mass_fr_xyz.shape[1] == 3
    ), "`total_body_center_of_mass_fr_xyz.shape[1]` should have 3 dimensions (X,Y,Z) "
