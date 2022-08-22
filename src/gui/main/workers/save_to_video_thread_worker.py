import logging

from PyQt6.QtCore import QThread

from src.cameras.persistence.video_writer.video_recorder import VideoRecorder

logger = logging.getLogger(__name__)


class SaveToVideoThreadWorker(QThread):
    def __init__(self, video_recorder: VideoRecorder):
        super().__init__()
        self._video_recorder = video_recorder

    def run(self):
        pass
