import logging
import threading

from PyQt6.QtCore import pyqtSignal, QThread

from freemocap.utilities.download_sample_data import download_sample_data
from freemocap.system.paths_and_filenames.file_and_folder_names import FIGSHARE_SAMPLE_ZIP_FILE_URL

logger = logging.getLogger(__name__)


class DownloadSampleDataThreadWorker(QThread):
    finished = pyqtSignal()
    in_progress = pyqtSignal(str)

    def __init__(self, kill_thread_event: threading.Event, parent=None):
        super().__init__(parent=parent)
        logger.info("Initializing download sample data thread worker")
        self._kill_thread_event = kill_thread_event

        self._work_done = False

    @property
    def work_done(self):
        return self._work_done

    def _emit_in_progress_data(self, message: str):
        self.in_progress.emit(message)

    def run(self):
        logger.info("Downloading sample data")

        try:
            self.sample_data_path = download_sample_data(sample_data_zip_file_url=FIGSHARE_SAMPLE_ZIP_FILE_URL)
            self.success = True
            logger.info("Sample data successfully downloaded")

        except Exception as e: # noqa
            self.success = False
            logger.error("Something went wrong while downloading sample data")

        self.finished.emit()
        self._work_done = True
