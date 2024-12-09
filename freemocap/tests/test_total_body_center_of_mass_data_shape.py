from pathlib import Path
from typing import Union

import numpy as np
import pytest

from freemocap.utilities.get_number_of_frames_of_videos_in_a_folder import (
    get_number_of_frames_of_videos_in_a_folder,
)


@pytest.mark.usefixtures("total_body_center_of_mass_data")
def test_total_body_center_of_mass_data_exists(
    total_body_center_of_mass_data: Union[str, Path],
):
    assert Path(
        total_body_center_of_mass_data
    ).is_file(), f"No file found at {total_body_center_of_mass_data}"


@pytest.mark.usefixtures("synchronized_video_folder_path", "total_body_center_of_mass_data")
def test_total_body_center_of_mass_data_shape(
    synchronized_video_folder_path: Union[str, Path],
    total_body_center_of_mass_data: Union[str, Path, np.ndarray],
):
    if isinstance(total_body_center_of_mass_data, (str, Path)):
        total_body_center_of_mass_fr_xyz = np.load(total_body_center_of_mass_data)
    else:
        total_body_center_of_mass_fr_xyz = total_body_center_of_mass_data

    frame_counts = list(get_number_of_frames_of_videos_in_a_folder(synchronized_video_folder_path).values())
    assert (
        len(set(frame_counts)) == 1
    ), f"Videos in {synchronized_video_folder_path} have different frame counts: {frame_counts}"

    number_of_frames = frame_counts[0]

    assert (
        total_body_center_of_mass_fr_xyz.shape[0] == number_of_frames
    ), f"Number of frames in {total_body_center_of_mass_fr_xyz.shape} does not match number of frames of videos in {synchronized_video_folder_path}"

    assert (
        total_body_center_of_mass_fr_xyz.shape[1] == 3
    ), f"total body center of mass should have 3 dimensions (X,Y,Z) but has {total_body_center_of_mass_fr_xyz.shape[1]}"

