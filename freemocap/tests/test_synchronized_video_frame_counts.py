from pathlib import Path
from typing import Union

from freemocap.tests.utilities.get_number_of_frames_of_videos_in_a_folder import (
    get_number_of_frames_of_videos_in_a_folder,
)
from freemocap.utilities.get_video_paths import get_video_paths


def test_synchronized_video_frame_counts(video_folder_path: Union[Path, str]):
    """
    Test if all the videos in this folder have precisely the same number of frames
    """
    list_of_video_paths = get_video_paths(Path(video_folder_path))

    assert len(list_of_video_paths) > 0, f"No videos found in {video_folder_path}"

    frame_count = get_number_of_frames_of_videos_in_a_folder(video_folder_path)

    assert (
        len(set(frame_count)) == 1
    ), f"Videos in {video_folder_path} have different frame counts: {frame_count}"

    return True
