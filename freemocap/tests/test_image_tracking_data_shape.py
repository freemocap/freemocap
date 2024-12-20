from pathlib import Path
from typing import Union

import numpy as np
import pytest

from freemocap.utilities.get_number_of_frames_of_videos_in_a_folder import (
    get_number_of_frames_of_videos_in_a_folder,
)
from freemocap.utilities.get_video_paths import get_video_paths


@pytest.mark.usefixtures("synchronized_video_folder_path", "image_tracking_data")
def test_image_tracking_data_exists(
    synchronized_video_folder_path: Union[str, Path],
    image_tracking_data: Union[str, Path],
):
    """
    test that the `2d detection` process worked correctly by checking that there is an `.npy` file containing the 2d data in the `output_data_folder`
    """

    assert Path(image_tracking_data).is_file(), f"{image_tracking_data} is not a file"


@pytest.mark.usefixtures("synchronized_video_folder_path", "image_tracking_data")
def test_image_tracking_data_shape(
    synchronized_video_folder_path: Union[str, Path],
    image_tracking_data: Union[str, Path, np.ndarray],
):
    """
    test that the `2d detection` process worked correctly by checking:

    The dimensions of that `npy` (number of cameras, number of frames, [ need to do - number of tracked points], [pixelX, pixelY] matches the videos in the `synchronized videos` folder

    TODO - check number of tracked points vs 'expected' number of tracked points
    """
    if isinstance(image_tracking_data, (str, Path)):
        image2d_camera_frame_marker_xyz = np.load(image_tracking_data)
    else:
        image2d_camera_frame_marker_xyz = image_tracking_data

    list_of_video_paths = get_video_paths(Path(synchronized_video_folder_path))
    number_of_videos = len(list_of_video_paths)
    assert (
        image2d_camera_frame_marker_xyz.shape[0] == number_of_videos
    ), f"Number of videos in image_tracking_data ({image2d_camera_frame_marker_xyz.shape[0]}) does not match number of videos in synchronized videos folder ({number_of_videos})"

    frame_counts = list(get_number_of_frames_of_videos_in_a_folder(synchronized_video_folder_path).values())

    assert (
        len(set(frame_counts)) == 1
    ), f"Videos in {synchronized_video_folder_path} have different frame counts: {frame_counts}"
    assert (
        image2d_camera_frame_marker_xyz.shape[1] == frame_counts[0]
    ), f"Number of frames in image_tracking_data does not match number of frames of videos in {synchronized_video_folder_path}"

    # TODO - check number of tracked points vs 'expected' number of tracked points

    assert (
        image2d_camera_frame_marker_xyz.shape[3] == 3
    ), f"Data has {image2d_camera_frame_marker_xyz.shape[3]} dimensions, expected 3 dimensions"
