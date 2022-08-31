import time

from PyQt6 import QtCore
from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QLabel,
    QSpacerItem,
)

from src.cameras.detection.models import FoundCamerasResponse
from src.config.webcam_config import WebcamConfig

from src.gui.main.main_window.middle_panel_viewers.camera_stream_grid_view import (
    CameraStreamGridView,
)
from src.gui.main.qt_utils.clear_layout import clear_layout
from src.gui.main.styled_widgets.page_title import PageTitle
from src.gui.main.workers.cam_detection_thread_worker import CameraDetectionThreadWorker

import logging

logger = logging.getLogger(__name__)


class CameraViewPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._frame = QFrame()
        self._frame.setFrameShape(QFrame.Shape.StyledPanel)
        self._layout = QVBoxLayout()
        self._frame.setLayout(self._layout)

        self._welcome_to_freemocap_title_widget = self._welcome_to_freemocap_title()
        self._layout.addWidget(self._welcome_to_freemocap_title_widget)

        self._camera_stream_grid_view = CameraStreamGridView()

    @property
    def frame(self):
        return self._frame

    @property
    def camera_stream_grid_view(self):
        return self._camera_stream_grid_view

    def _welcome_to_freemocap_title(self):
        # TO DO - this shouldn't be part of the `camera_view_panel` - it should be its own thing that gets swapped out on session start
        logger.info("Creating `welcome to freemocap` widget")
        welcome_widget = QWidget()
        layout = QVBoxLayout()
        welcome_widget.setLayout(layout)

        layout.addStretch()

        session_title_widget = PageTitle(
            "Welcome  to  FreeMoCap! \n  \U00002728 \U0001F480 \U00002728 "
        )
        layout.addWidget(session_title_widget, QtCore.Qt.AlignCenter)

        alpha_version_text_str = "Please note! This is an *early* version of the `alpha` version of this software, so like - Manage your Expectations lol "
        layout.addWidget(QLabel(alpha_version_text_str), QtCore.Qt.AlignCenter)

        layout.addStretch()

        return welcome_widget

    def show_camera_streams(self):

        try:
            self._welcome_to_freemocap_title_widget.close()
        except:
            pass

        logger.info("Showing camera stream grid view")
        self._layout.addWidget(self._camera_stream_grid_view)
