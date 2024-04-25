import logging
from pathlib import Path

from PySide6.QtCore import Signal, QThread

from freemocap.utilities.download_sample_data import download_sample_data

logger = logging.getLogger(__name__)


class DownloadDataThreadWorker(QThread):
    finished = Signal(str)
    in_progress = Signal(str)

    def __init__(self, dowload_url: str, parent=None):
        super().__init__(parent=parent)
        logger.debug("Initializing download sample data thread worker")
        self.download_url = dowload_url

    def run(self):
        logger.debug("Downloading sample data")

        try:
            downloaded_data_path = download_sample_data(sample_data_zip_file_url=self.download_url)
            if Path(downloaded_data_path).exists():
                logger.debug(f"Data successfully downloaded from: {self.download_url}")
                self.finished.emit(downloaded_data_path)
            else:
                logger.error(f"Could not find downloaded data at {downloaded_data_path}")
                raise FileNotFoundError(f"Could not find downloaded data at {downloaded_data_path}")

        except Exception as e:  # noqa
            logger.exception(e)
            logger.error(f"Error downloading sample data from {self.download_url}")
            raise e
