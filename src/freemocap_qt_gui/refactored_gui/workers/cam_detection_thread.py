from PyQt6.QtCore import QObject, pyqtSignal

from src.cameras.detection.cam_singleton import get_or_create_cams


class CamDetectionWorker(QObject):
    finished = pyqtSignal()

    def run(self):
        get_or_create_cams()
        self.finished.emit()
