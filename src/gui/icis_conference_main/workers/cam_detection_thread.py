from old_src.cameras.detection.cam_singleton import get_or_create_cams
from old_src.cameras.detection.models import FoundCamerasResponse
from PyQt6.QtCore import pyqtSignal, QThread


class CamDetectionWorker(QThread):
    finished = pyqtSignal(FoundCamerasResponse)

    def run(self):
        cams = get_or_create_cams(always_create=True)
        self.finished.emit(cams)
