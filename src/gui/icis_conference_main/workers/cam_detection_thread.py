from PyQt6.QtCore import QThread, pyqtSignal

from src.cameras.detection.cam_singleton import get_or_create_cams
from src.cameras.detection.models import FoundCamerasResponse


class CamDetectionWorker(QThread):
    finished = pyqtSignal(FoundCamerasResponse)

    def run(self):
        cams = get_or_create_cams(always_create=True)
        self.finished.emit(cams)
