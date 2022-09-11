import enum
from pathlib import Path
from typing import Union

import cv2
import numpy as np
from PyQt6 import QtGui
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWidgets import QHBoxLayout, QWidget, QLabel

import logging


from src.gui.main.app_state.app_state import APP_STATE

logger = logging.getLogger(__name__)


class VideoPlayerWidget(QWidget):
    def __init__(self):
        super().__init__()

        self._video_view_label = QLabel()
        # self._video.setScaledContents(True)
        layout = QHBoxLayout()
        layout.addWidget(self._video_view_label)

        self.setLayout(layout)

    def update_image(self, image: np.ndarray):
        q_image = QImage(
            image.data,
            image.shape[1],
            image.shape[0],
            QImage.Format.Format_RGB888,
        )
        # q_image = q_image.scaledToWidth(
        #     APP_STATE.main_window_width / len(APP_STATE.available_cameras)
        # )

        q_image = q_image.scaledToWidth(200)

        self._pixmap = QPixmap.fromImage(q_image)
        self._video_view_label.setPixmap(self._pixmap)

    def resizeEvent(self, a0: QtGui.QResizeEvent) -> None:
        logging.debug(f"window resized")

        # TO DO - Some kinda something here to make the videos scale properly and keep their aspect ratio

        # self._pixmap.scaled(
        #     self.width(), self.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        # )
