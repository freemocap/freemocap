from PyQt6.QtCore import QThread, pyqtSignal

from src.cameras.detection.cam_singleton import get_or_create_cams
from src.cameras.detection.models import FoundCamerasResponse

import logging

logger = logging.getLogger(__name__)


class MinimalExampleThreadWorker(QThread):
    finished = pyqtSignal(str)

    def run(self):
        self.finished.emit("Done!")
