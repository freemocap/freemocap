from typing import List, Dict, Callable

import cv2
import numpy as np
from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QGridLayout,
    QVBoxLayout,
    QLabel,
    QDockWidget,
    QPushButton,
    QHBoxLayout,
)

from src.cameras.detection.models import FoundCamerasResponse
from src.cameras.save_synchronized_videos import save_synchronized_videos
from src.config.webcam_config import WebcamConfig
from src.gui.main.app_state.app_state import APP_STATE
from src.gui.main.custom_widgets.single_camera_widget import SingleCameraWidget
from src.gui.main.qt_utils.clear_layout import clear_layout

import logging

logger = logging.getLogger(__name__)


class CameraStreamGridView(QWidget):
    cameras_connected_signal = pyqtSignal()

    def __init__(self):
        super().__init__()

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        # for landscape camera streams (e.g. rotate 0 or 180 degrees)
        self._horizontal_layout = QHBoxLayout()
        self._layout.addLayout(self._horizontal_layout)

        # for portrait camera streams (e.g. rotate 90 or 270 degrees)
        self._vertical_layout = QVBoxLayout()
        self._layout.addLayout(self._vertical_layout)

    def create_and_start_camera_widgets(
        self,
        dictionary_of_webcam_configs=Dict[str, WebcamConfig],
        pop_out_camera_windows: bool = False,
    ):
        logger.info("Creating camera widgets...")

        if hasattr(self, "_dictionary_of_camera_widgets"):
            self.close_camera_widgets()

        clear_layout(self._horizontal_layout)
        clear_layout(self._vertical_layout)

        self._dictionary_of_camera_configs = dictionary_of_webcam_configs
        self._dictionary_of_camera_widgets = {}

        for webcam_config in dictionary_of_webcam_configs.values():
            id = str(webcam_config.webcam_id)
            self._dictionary_of_camera_widgets[id] = SingleCameraWidget(webcam_config)

            if pop_out_camera_windows:
                self._dictionary_of_camera_widgets[id].setWindowTitle(f"Camera {id}")
                self._dictionary_of_camera_widgets[id].show()
            else:
                if (
                    webcam_config.rotate_video_cv2_code == None
                    or webcam_config.rotate_video_cv2_code == cv2.ROTATE_180
                ):
                    self._vertical_layout.addWidget(
                        self._dictionary_of_camera_widgets[id]
                    )
                else:
                    self._horizontal_layout.addWidget(
                        self._dictionary_of_camera_widgets[id]
                    )
        self.start_camera_widgets()

    def start_camera_widgets(self):
        if hasattr(self, "_dictionary_of_camera_widgets"):
            logger.info("Starting cameras")
            for camera_widget in self._dictionary_of_camera_widgets.values():
                camera_widget.start()
            self.cameras_connected_signal.emit()

    def close_camera_widgets(self):
        if hasattr(self, "_dictionary_of_camera_widgets"):
            logger.info("Quitting running cameras")
            for camera_widget in self._dictionary_of_camera_widgets.values():
                camera_widget.quit()
                camera_widget.close()

    def start_recording_videos(self):
        for camera_widget in self._dictionary_of_camera_widgets.values():
            camera_widget.start_saving_frames()

    def stop_recording_videos(self):
        for camera_widget in self._dictionary_of_camera_widgets.values():
            camera_widget.stop_saving_frames()

    def gather_video_recorders(self):
        video_recorders = {}
        for camera_id, camera_widget in self._dictionary_of_camera_widgets.items():
            video_recorders[camera_id] = camera_widget.video_recorder

        return video_recorders

    def reset_video_recorders(self):
        for camera_widget in self._dictionary_of_camera_widgets.values():
            camera_widget.reset_video_recorder()

    def hideEvent(self, a0: QtGui.QHideEvent) -> None:
        self.close_camera_widgets()
