import logging
import threading
from pathlib import Path

from PyQt6.QtCore import pyqtSignal, QThread

from skelly_synchronize.skelly_synchronize import synchronize_videos_from_audio

logger = logging.getLogger(__name__)


class SynchronizeVideosThreadWorker(QThread):
    finished = pyqtSignal()
    in_progress = pyqtSignal(str)

    def __init__(
        self,
        raw_video_folder_path: Path,
        synchronized_video_folder_path: Path,
        kill_thread_event: threading.Event,
    ):
        super().__init__()
        logger.info("Initializing Synchronize Videos Thread Worker")
        self._kill_thread_event = kill_thread_event
        self._raw_video_folder_path = raw_video_folder_path
        self._synchronized_video_folder_path = synchronized_video_folder_path

        self.output_folder_path = None

        self._work_done = False

    @property
    def work_done(self):
        return self._work_done

    def _emit_in_progress_data(self, message: str):
        self.in_progress.emit(message)

    def run(self):
        logger.info("Beginning to synchronize videos")

        try:
            self.output_folder_path = synchronize_videos_from_audio(
                raw_video_folder_path=self._raw_video_folder_path,
                synchronized_video_folder_path=self._synchronized_video_folder_path,
                create_debug_plots_bool=False,
            )

        except Exception as e:
            logger.exception("Something went wrong while synchronizing videos")
            logger.exception(e)

        self.finished.emit()
        self._work_done = True

        logger.info("Synchronizing Videos Complete")
