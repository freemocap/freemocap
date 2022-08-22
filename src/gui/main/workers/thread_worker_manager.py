from pathlib import Path
from typing import Dict, Union

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

from src.cameras.detection.models import FoundCamerasResponse
from src.config.webcam_config import WebcamConfig
from src.gui.main.custom_widgets.single_camera_widget import CameraWidget
from src.gui.main.workers.cam_detection_thread_worker import CameraDetectionThreadWorker

import logging

from src.gui.main.workers.save_to_video_thread_worker import SaveToVideoThreadWorker

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
        logger.info("creating camera widgets with running threads")

        self._camera_widgets = []
        dictionary_of_single_camera_layouts = {}
        for webcam_config in dictionary_of_webcam_configs.values():
            camera_widget = CameraWidget(webcam_config)
            camera_widget.start()

            camera_layout = QVBoxLayout()
            camera_layout.addWidget(QLabel(f"Camera {str(webcam_config.webcam_id)}"))
            camera_layout.addWidget(camera_widget)

            dictionary_of_single_camera_layouts[webcam_config.webcam_id] = camera_layout

            self._camera_widgets.append(camera_widget)

        self.cameras_connected_signal.emit(dictionary_of_single_camera_layouts)

    def start_recording_videos(self):
        logger.info("starting to save frames in camera streams for later recording")
        for camera_widget in self._camera_widgets:
            camera_widget.start_saving_frames()

    def stop_recording_videos(self):
        logger.info("stopping saving frames in camera streams")
        for camera_widget in self._camera_widgets:
            camera_widget.stop_saving_frames()

    def launch_save_videos_thread_worker(
        self, folder_to_save_videos: [Union[str, Path]]
    ):
        logger.info("Launching save videos thread worker...")

        dictionary_of_video_recorders = {}
        for camera_widget in self._camera_widgets:
            dictionary_of_video_recorders[
                str(camera_widget.camera_id)
            ] = camera_widget.video_recorder

        self._save_to_video_thread_worker = SaveToVideoThreadWorker(
            dictionary_of_video_recorders=dictionary_of_video_recorders,
            folder_to_save_videos=folder_to_save_videos,
        )
        self._save_to_video_thread_worker.start()
