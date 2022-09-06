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
from src.gui.main.main_window.left_panel_controls.toolbox_widgets.welcome_create_or_load_new_session_panel import (
    WelcomeCreateOrLoadNewSessionPanel,
)

from src.gui.main.main_window.middle_panel_viewers.camera_stream_grid_view import (
    CameraStreamGridView,
)
from src.gui.main.qt_utils.clear_layout import clear_layout
from src.gui.main.styled_widgets.page_title import PageTitle
from src.gui.main.workers.cam_detection_thread_worker import CameraDetectionThreadWorker

import logging

logger = logging.getLogger(__name__)


class MiddleViewingPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._frame = QFrame()
        self._frame.setFrameShape(QFrame.Shape.StyledPanel)
        self._layout = QVBoxLayout()
        self._frame.setLayout(self._layout)
        self._welcome_create_or_load_session_panel = (
            WelcomeCreateOrLoadNewSessionPanel()
        )
        self._layout.addWidget(self._welcome_create_or_load_session_panel)

        self._camera_stream_grid_view = CameraStreamGridView()

    @property
    def frame(self):
        return self._frame

    @property
    def welcome_create_or_load_session_panel(self):
        return self._welcome_create_or_load_session_panel

    @property
    def camera_stream_grid_view(self):
        return self._camera_stream_grid_view

    def show_camera_streams(self):

        try:
            self._welcome_create_or_load_session_panel.close()
        except:
            pass

        logger.info("Showing camera stream grid view")
        self._layout.addWidget(self._camera_stream_grid_view)
