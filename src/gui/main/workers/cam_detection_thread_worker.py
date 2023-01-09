import logging

from old_src.cameras.detection.cam_singleton import get_or_create_cams
from old_src.cameras.detection.models import FoundCamerasResponse
from PyQt6.QtCore import pyqtSignal, QThread

logger = logging.getLogger(__name__)


class CameraDetectionThreadWorker(QThread):
    finished = pyqtSignal(FoundCamerasResponse)

    def __init__(self):
        super().__init__()

    def run(self):
        logger.info("Detecting cameras....")
        found_cameras_response = get_or_create_cams(always_create=True)
        logger.info(f"Cameras detected: {found_cameras_response}")
        self.finished.emit(found_cameras_response)
