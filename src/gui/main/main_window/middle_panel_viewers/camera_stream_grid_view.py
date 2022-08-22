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
        self._camera_widgets = []

        self._camera_stream_layout = QVBoxLayout()
        self.setLayout(self._camera_stream_layout)

    @property
    def video_recorders(self):
        return [cam.video_recorder for cam in self._camera_widgets]

    def show_camera_streams(
        self, dictionary_of_single_camera_layouts=(Dict[str, QVBoxLayout])
    ):
        clear_layout(self._camera_stream_layout)
        for single_camera_layout in dictionary_of_single_camera_layouts.values():
            self._camera_stream_layout.addLayout(single_camera_layout)

    def close_all_camera_streams(self):
        for camera_widget in self._camera_widgets:
            camera_widget.quit()

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

    def close_and_reconnect_to_cameras(self):
        self.close_all_camera_streams()
        self._camera_widgets = []
        clear_layout(self._camera_stream_layout)
        self.connect_to_camera_streams()
