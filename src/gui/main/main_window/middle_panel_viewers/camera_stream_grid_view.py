from typing import List, Dict

import numpy as np
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QGridLayout, QVBoxLayout, QLabel

from src.cameras.detection.models import FoundCamerasResponse
from src.cameras.save_synchronized_videos import save_synchronized_videos
from src.config.webcam_config import WebcamConfig
from src.gui.main.app_state.app_state import APP_STATE
from src.gui.main.custom_widgets.single_camera_widget import CameraWidget
from src.gui.main.qt_utils.clear_layout import clear_layout

import logging

logger = logging.getLogger(__name__)


class CameraStreamGridView(QWidget):
    cameras_connected_signal = pyqtSignal()

    def __init__(self):
        super().__init__()

        self._camera_stream_layout = QVBoxLayout()
        self.setLayout(self._camera_stream_layout)

    @property
    def video_recorders(self):
        return [cam.video_recorder for cam in self._camera_widgets]

    def create_and_start_camera_widgets(
        self, dictionary_of_webcam_configs=Dict[str, WebcamConfig]
    ):
        logger.info("creating camera widgets")
        clear_layout(self._camera_stream_layout)

        try:
            self.close_camera_widgets()
        except:
            pass

        self._camera_configs_dict = dictionary_of_webcam_configs
        self._camera_widgets = {}

        for webcam_config in dictionary_of_webcam_configs.values():
            self._camera_widgets[str(webcam_config.webcam_id)] = CameraWidget(
                webcam_config
            )
            camera_layout = QVBoxLayout()
            camera_layout.addWidget(QLabel(f"Camera {str(webcam_config.webcam_id)}"))
            camera_layout.addWidget(self._camera_widgets[str(webcam_config.webcam_id)])
            self._camera_stream_layout.addLayout(camera_layout)

        self._start_camera_workers()

    def close_camera_widgets(self):
        logger.info("Quitting running cameras")
        for camera_widget in self._camera_widgets:
            camera_widget.quit()

    def _start_camera_workers(self):
        for webcam_id in self._camera_configs_dict.keys():
            self._camera_widgets[webcam_id].start()
        self.cameras_connected_signal.emit()

    def start_recording_videos(self):
        for camera_widget in self._camera_widgets:
            camera_widget.start_saving_frames()

    def stop_recording_videos(self):
        for camera_widget in self._camera_widgets:
            camera_widget.stop_saving_frames()

    def save_synchronized_videos(self):
        video_recorders = []
        for cam in self._camera_widgets:
            video_recorders.append(cam.video_recorder)

    def _reset_video_recorders(self):
        for camera_widget in self._camera_widgets:
            camera_widget.reset_video_recorder()
