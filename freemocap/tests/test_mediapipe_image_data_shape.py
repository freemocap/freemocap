import pytest
from pathlib import Path
from typing import Union

import numpy as np

from freemocap.tests.utilities.get_number_of_frames_of_videos_in_a_folder import (
    get_number_of_frames_of_videos_in_a_folder,
)


@pytest.mark.usefixtures("synchronized_video_folder_path", "image_data_file_name")
def test_mediapipe_image_shape(
    synchronized_video_folder_path: Union[str, Path],
    image_data_file_name,
):

    """
    test that the `mediapipe image detection` process worked correctly by checking:
    1. There is an `.npy` file containing the mediapipe image data in the `output_data_folder`
    2. The dimensions of that `npy` (number of cameras, number of frames, [ need to do - number of tracked points], [pixelX, pixelY] matches the videos in the `synchronized videos` folder
    TODO - check number of tracked points vs 'expected' number of tracked points
    """

    assert Path(image_data_file_name).is_file(), f"{image_data_file_name} is not a file"

    mediapipe_2d_data = np.load(image_data_file_name)

    list_of_video_paths = list(Path(synchronized_video_folder_path).glob("*.mp4"))
    number_of_videos = len(list_of_video_paths)
    assert mediapipe_2d_data.shape[0] == number_of_videos

    frame_count = get_number_of_frames_of_videos_in_a_folder(synchronized_video_folder_path)

    assert (
        len(set(frame_count)) == 1
    ), f"Videos in {synchronized_video_folder_path} have different frame counts: {frame_count}"
    assert (
        mediapipe_2d_data.shape[1] == frame_count[0]
    ), f"Number of frames in {image_data_file_name} does not match number of frames of videos in {synchronized_video_folder_path}"

    # TODO - check number of tracked points vs 'expected' number of tracked points

    assert mediapipe_2d_data.shape[3] == 2

    return True