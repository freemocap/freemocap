from typing import Dict

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

from src.cameras.detection.models import FoundCamerasResponse
from src.config.webcam_config import WebcamConfig
from src.gui.main.custom_widgets.single_camera_widget import CameraWidget
from src.gui.main.workers.cam_detection_thread_worker import CameraDetectionThreadWorker

import logging

logger = logging.getLogger(__name__)


class ThreadWorkerManager(QWidget):
    camera_detection_finished = pyqtSignal(FoundCamerasResponse)
    cameras_connected_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()

    def launch_detect_cameras_worker(self):
        logger.info("Launch camera detection worker")
        self._camera_detection_thread_worker = CameraDetectionThreadWorker()
        self._camera_detection_thread_worker.finished.connect(
            self.camera_detection_finished.emit
        )
        self._camera_detection_thread_worker.start()

    def create_camera_widgets_with_running_threads(
        self, dictionary_of_webcam_configs=Dict[str, WebcamConfig]
    ):
        self._dictionary_of_single_camera_layouts = {}
        for webcam_config in dictionary_of_webcam_configs.values():
            camera_widget = CameraWidget(webcam_config)
            camera_widget.capture()
            camera_layout = QVBoxLayout()
            camera_layout.addWidget(QLabel(f"Camera {str(webcam_config.webcam_id)}"))
            camera_layout.addWidget(camera_widget)
            self._dictionary_of_single_camera_layouts[
                webcam_config.webcam_id
            ] = camera_layout

        self.cameras_connected_signal.emit(self._dictionary_of_single_camera_layouts)
