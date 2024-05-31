from pathlib import Path
from typing import Optional, Union

import numpy as np
import pytest

from freemocap.utilities.get_number_of_frames_of_videos_in_a_folder import (
    get_number_of_frames_of_videos_in_a_folder,
)
from freemocap.utilities.get_video_paths import get_video_paths


@pytest.mark.usefixtures("synchronized_video_folder_path", "image_tracking_data_file_path")
def test_image_tracking_data_exists(
    synchronized_video_folder_path: Union[str, Path],
    image_tracking_data_file_path: Union[str, Path],
):
    """
    test that the `2d detection` process worked correctly by checking:

    There is an `.npy` file containing the 2d data in the `output_data_folder`
    2. The dimensions of that `npy` (number of cameras, number of frames, [ need to do - number of tracked points], [pixelX, pixelY] matches the videos in the `synchronized videos` folder

    TODO - check number of tracked points vs 'expected' number of tracked points
    """

    assert Path(image_tracking_data_file_path).is_file(), f"{image_tracking_data_file_path} is not a file"

    image_tracking_data = np.load(image_tracking_data_file_path)

    list_of_video_paths = get_video_paths(Path(synchronized_video_folder_path))
    number_of_videos = len(list_of_video_paths)
    assert (
        image_tracking_data.shape[0] == number_of_videos
    ), f"Number of videos in {image_tracking_data_file_path} does not match number of videos in synchronized videos folder"

    frame_counts = list(get_number_of_frames_of_videos_in_a_folder(synchronized_video_folder_path).values())

    assert (
        len(set(frame_counts)) == 1
    ), f"Videos in {synchronized_video_folder_path} have different frame counts: {frame_counts}"
    assert (
        image_tracking_data.shape[1] == frame_counts[0]
    ), f"Number of frames in {image_tracking_data_file_path} does not match number of frames of videos in {synchronized_video_folder_path}"

    # TODO - check number of tracked points vs 'expected' number of tracked points

    assert (
        image_tracking_data.shape[3] == 3
    ), f"Data has {image_tracking_data.shape[3]} dimensions, expected 3 dimensions"
    
@pytest.mark.usefixtures("synchronized_video_folder_path", "image_tracking_data_file_path")
def test_image_tracking_data_shape(
    synchronized_video_folder_path: Union[str, Path],
    image_tracking_data_file_path: Optional[Union[str, Path]] = None,
    image_tracking_data: Optional[np.ndarray] = None,
):
    """
    test that the `2d detection` process worked correctly by checking:

    The dimensions of that `npy` (number of cameras, number of frames, [ need to do - number of tracked points], [pixelX, pixelY] matches the videos in the `synchronized videos` folder

    TODO - check number of tracked points vs 'expected' number of tracked points
    """
    if image_tracking_data is None and image_tracking_data_file_path is None:
        raise ValueError("Must provide either image_tracking_data or image_tracking_data_file_path")
    elif image_tracking_data is None and image_tracking_data_file_path:
        image_tracking_data = np.load(image_tracking_data_file_path)

    list_of_video_paths = get_video_paths(Path(synchronized_video_folder_path))
    number_of_videos = len(list_of_video_paths)
    assert (
        image_tracking_data.shape[0] == number_of_videos
    ), f"Number of videos in image_tracking_data does not match number of videos in synchronized videos folder"

    frame_counts = list(get_number_of_frames_of_videos_in_a_folder(synchronized_video_folder_path).values())

    assert (
        len(set(frame_counts)) == 1
    ), f"Videos in {synchronized_video_folder_path} have different frame counts: {frame_counts}"
    assert (
        image_tracking_data.shape[1] == frame_counts[0]
    ), f"Number of frames in image_tracking_data does not match number of frames of videos in {synchronized_video_folder_path}"

    # TODO - check number of tracked points vs 'expected' number of tracked points

    assert (
        image_tracking_data.shape[3] == 3
    ), f"Data has {image_tracking_data.shape[3]} dimensions, expected 3 dimensions"
