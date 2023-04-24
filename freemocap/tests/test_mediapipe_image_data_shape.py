import pytest
import numpy as np
from pathlib import Path
from typing import Union

from freemocap.tests.utilities.get_number_of_frames_of_videos_in_a_folder import (
    get_number_of_frames_of_videos_in_a_folder,
)
from freemocap.utilities.get_video_paths import get_video_paths


@pytest.mark.usefixtures("synchronized_video_folder_path", "image_data_file_name")
def test_mediapipe_image_data_shape(
    synchronized_video_folder_path: Union[str, Path],
    image_data_file_name: Union[str, Path],
):
    """
    test that the `mediapipe 2d detection` process worked correctly by checking:

    1. There is an `.npy` file containing the mediapipe 2d data in the `output_data_folder`
    2. The dimensions of that `npy` (number of cameras, number of frames, [ need to do - number of tracked points], [pixelX, pixelY] matches the videos in the `synchronized videos` folder

    TODO - check number of tracked points vs 'expected' number of tracked points
    """

    assert Path(image_data_file_name).is_file(), f"{image_data_file_name} is not a file"

    image_data = np.load(image_data_file_name)

    list_of_video_paths = get_video_paths(Path(synchronized_video_folder_path))
    number_of_videos = len(list_of_video_paths)
    assert (
        image_data.shape[0] == number_of_videos
    ), f"Number of videos in {image_data_file_name} does not match number of videos in synchronized videos folder"

    frame_count = get_number_of_frames_of_videos_in_a_folder(synchronized_video_folder_path)

    assert (
        len(set(frame_count)) == 1
    ), f"Videos in {synchronized_video_folder_path} have different frame counts: {frame_count}"
    assert (
        image_data.shape[1] == frame_count[0]
    ), f"Number of frames in {image_data_file_name} does not match number of frames of videos in {synchronized_video_folder_path}"

    # TODO - check number of tracked points vs 'expected' number of tracked points

    assert image_data.shape[3] == 3, f"Data has {image_data.shape[3]} dimensions, expected 3 dimensions"

