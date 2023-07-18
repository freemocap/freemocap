import logging
from pathlib import Path
from typing import Union

import cv2

from freemocap.utilities.get_video_paths import get_video_paths

logger = logging.getLogger(__name__)


def get_number_of_frames_of_videos_in_a_folder(folder_path: Union[str, Path]):
    """
    Get the number of frames in the first video in a folder
    """

    list_of_video_paths = get_video_paths(Path(folder_path))

    if len(list_of_video_paths) == 0:
        logger.error(f"No videos found in {folder_path}")
        return None

    frame_count = []
    for video_path in list_of_video_paths:
        cap = cv2.VideoCapture(str(video_path))
        frame_count.append(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
        cap.release()

    return frame_count
