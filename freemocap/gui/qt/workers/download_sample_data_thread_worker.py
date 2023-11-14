import logging
from pathlib import Path

from PyQt6.QtCore import pyqtSignal, QThread

from freemocap.utilities.download_sample_data import download_sample_data

logger = logging.getLogger(__name__)


class DownloadDataThreadWorker(QThread):
    finished = pyqtSignal(str)
    in_progress = pyqtSignal(str)

    def __init__(self,
                 dowload_url: str,
                 parent=None):
        super().__init__(parent=parent)
        logger.info("Initializing download sample data thread worker")
        self.download_url = dowload_url

    def run(self):
        logger.info("Downloading sample data")

        try:
            downloaded_data_path = download_sample_data(sample_data_zip_file_url=self.download_url)
            if Path(downloaded_data_path).exists():
                logger.info(f"Data successfully downloaded from: {self.download_url}")
                self.finished.emit(downloaded_data_path)
            else:
                logger.error(f"Could not find downloaded data at {downloaded_data_path}")
                raise FileNotFoundError(f"Could not find downloaded data at {downloaded_data_path}")

        except Exception as e: # noqa
            logger.exception(e)
            logger.error(f"Error downloading sample data from {self._dowload_url}")
            raise e
