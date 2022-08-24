import time

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QWidget

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
        self._central_layout = QVBoxLayout()
        self._central_layout.addWidget(self._welcome_to_freemocap_title_widget)
        self._layout.addLayout(self._central_layout)

        self._camera_stream_grid_view = None

    @property
    def frame(self):
        return self._frame

    @property
    def camera_stream_grid_view(self):
        return self._camera_stream_grid_view

    def _welcome_to_freemocap_title(self):
        session_title = PageTitle(
            "Welcome  to  FreeMoCap! \n  \U00002728 \U0001F480 \U00002728 "
        )
        return session_title

    def reconnect_to_cameras(self):
        self._camera_stream_grid_view.close_and_reconnect_to_cameras()

    def show_camera_streams(self, dictionary_of_single_camera_layouts):

        clear_layout(self._central_layout)

        self._camera_stream_grid_view = CameraStreamGridView()

        self._camera_stream_grid_view.show_camera_streams(
            dictionary_of_single_camera_layouts
        )
        logger.info("Showing camera stream grid view")
        self._central_layout.addWidget(self._camera_stream_grid_view)
