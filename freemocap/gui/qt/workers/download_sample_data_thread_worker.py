import logging
from pathlib import Path

from PySide6.QtCore import Signal, QThread

from freemocap.utilities.download_sample_data import download_dataset

logger = logging.getLogger(__name__)


class DownloadDataThreadWorker(QThread):
    finished = Signal(str)
    in_progress = Signal(str)

    def __init__(self, dataset_name: str, parent=None):
        super().__init__(parent=parent)
        logger.debug("Initializing download sample data thread worker")
        self.dataset_name = dataset_name

    def run(self):
        logger.debug("Starting sample data download")

        try:
            downloaded_data_path = download_dataset(self.dataset_name)
            if Path(downloaded_data_path).exists():
                logger.debug(f"Data successfully downloaded to {downloaded_data_path}")
                self.finished.emit(downloaded_data_path)
            else:
                logger.error(f"Could not find downloaded data at {downloaded_data_path}")
                raise FileNotFoundError(f"Could not find downloaded data at {downloaded_data_path}")

        except Exception as e:  # noqa
            logger.exception(e)
            logger.error("Error downloading sample data")
            raise e
