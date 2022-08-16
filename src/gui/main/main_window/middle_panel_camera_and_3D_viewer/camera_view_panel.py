import cv2
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QWidget, QPushButton

from src.cameras.detection.cam_singleton import (
    get_or_create_cams,
    get_or_create_cams_list,
)
from src.config.webcam_config import WebcamConfig
from src.gui.icis_conference_main.workflows.camera_configuration import (
    CameraConfiguration,
)
from src.gui.main.app_state.app_state import APP_STATE
from src.gui.main.main_window.middle_panel_camera_and_3D_viewer.camera_stream_grid_view import (
    CameraStreamGridView,
)
from src.gui.main.qt_utils.clear_layout import clear_layout
from src.gui.main.styled_widgets.page_title import PageTitle


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

        self._camera_stream_grid_view = CameraStreamGridView()

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

    def detect_and_connect_to_cameras(self):
        self.detect_cameras()
        self._connect_to_cameras()

    def detect_cameras(self):
        clear_layout(self._central_layout)
        self._central_layout.addWidget(PageTitle("Detecting Cameras..."))

        found_camera_ids_list = get_or_create_cams_list()

        APP_STATE.available_cameras = found_camera_ids_list

        APP_STATE.selected_cameras = APP_STATE.available_cameras

        for camera_id in APP_STATE.selected_cameras:
            APP_STATE.camera_configs[camera_id] = WebcamConfig(webcam_id=camera_id)

    def _connect_to_cameras(self):
        self._camera_stream_grid_view.connect_to_camera_streams()

        clear_layout(self._central_layout)
        self._central_layout.addWidget(self._camera_stream_grid_view)

    def reconnect_to_cameras(self):
        self._camera_stream_grid_view.close_all_camera_streams()
        self._connect_to_cameras()
