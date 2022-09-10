import logging
from pathlib import Path
from typing import Union, Dict

from PyQt6.QtCore import QThread

from src.cameras.persistence.video_writer.video_recorder import VideoRecorder
from src.cameras.save_synchronized_videos import save_synchronized_videos

logger = logging.getLogger(__name__)


class SaveToVideoThreadWorker(QThread):
    def __init__(
        self,
        dictionary_of_video_recorders: Dict[str, VideoRecorder],
        folder_to_save_videos: Union[str, Path],
    ):
        super().__init__()
        self._dictionary_of_video_recorders = dictionary_of_video_recorders
        self._folder_to_save_videos = folder_to_save_videos

    def run(self):
        save_synchronized_videos(
            self._dictionary_of_video_recorders, self._folder_to_save_videos
        )
