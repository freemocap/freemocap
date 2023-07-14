from pathlib import Path
from typing import Union

import pytest

from freemocap.utilities.get_number_of_frames_of_videos_in_a_folder import (
    get_number_of_frames_of_videos_in_a_folder,
)
from freemocap.utilities.get_video_paths import get_video_paths


@pytest.mark.usefixtures("synchronized_video_folder_path")
def test_synchronized_video_frame_counts(synchronized_video_folder_path: Union[Path, str]):
    """
    Test if all the videos in this folder have precisely the same number of frames
    """
    list_of_video_paths = get_video_paths(Path(synchronized_video_folder_path))

    assert len(list_of_video_paths) > 0, f"No videos found in {synchronized_video_folder_path}"

    frame_count = get_number_of_frames_of_videos_in_a_folder(synchronized_video_folder_path)

    assert (
        len(set(frame_count)) == 1
    ), f"Videos in {synchronized_video_folder_path} have different frame counts: {frame_count}"
