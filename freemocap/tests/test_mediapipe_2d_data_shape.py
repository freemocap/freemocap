from pathlib import Path
from typing import Union

import numpy as np

from freemocap.tests.utilities.get_number_of_frames_of_videos_in_a_folder import (
    get_number_of_frames_of_videos_in_a_folder,
)


def test_mediapipe_image_data_shape(
    synchronized_videos_folder: Union[str, Path],
    mediapipe_image_data_file_path: Union[str, Path],
):

    """
    test that the `mediapipe image detection` process worked correctly by checking:

    1. There is an `.npy` file containing the mediapipe image data in the `output_data_folder`
    2. The dimensions of that `npy` (number of cameras, number of frames, [ need to do - number of tracked points], [pixelX, pixelY] matches the videos in the `synchronized videos` folder

    TODO - check number of tracked points vs 'expected' number of tracked points
    """

    assert Path(
        mediapipe_image_data_file_path
    ).is_file(), f"{mediapipe_image_data_file_path} is not a file"

    mediapipe_image_data = np.load(mediapipe_image_data_file_path)

    list_of_video_paths = list(Path(synchronized_videos_folder).glob("*.mp4"))
    number_of_videos = len(list_of_video_paths)
    assert mediapipe_image_data.shape[0] == number_of_videos

    frame_count = get_number_of_frames_of_videos_in_a_folder(synchronized_videos_folder)

    assert (
        len(set(frame_count)) == 1
    ), f"Videos in {synchronized_videos_folder} have different frame counts: {frame_count}"
    assert (
        mediapipe_image_data.shape[1] == frame_count[0]
    ), f"Number of frames in {mediapipe_image_data_file_path} does not match number of frames of videos in {synchronized_videos_folder}"

    # TODO - check number of tracked points vs 'expected' number of tracked points

    assert mediapipe_image_data.shape[3] == 3  # the shape is now 3, x y z TODO - check in with Jon

    return True
