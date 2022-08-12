from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QWidget

from src.cameras.detection.cam_singleton import get_or_create_cams
from src.gui.icis_conference_main.workflows.camera_configuration import (
    CameraConfiguration,
)
from src.gui.main.app_state.app_state import APP_STATE
from src.gui.main.main_window.middle_panel_camera_and_3D_viewer.camera_stream_grid_view import (
    CameraStreamGridView,
)
from src.gui.main.qt_utils.clear_layout import clear_layout
from src.gui.main.styled_widgets.page_title import PageTitle


class ViewingPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._frame = QFrame()
        self._frame.setFrameShape(QFrame.Shape.StyledPanel)
        self._layout = QVBoxLayout()
        self._frame.setLayout(self._layout)

        self._layout.addWidget(self._welcome_to_freemocap_title())

    @property
    def frame(self):
        return self._frame

    @property
    def layout(self):
        return self._layout

    def _welcome_to_freemocap_title(self):
        session_title = PageTitle(
            "Welcome  to  FreeMoCap! \n  \U00002728 \U0001F480 \U00002728 "
        )
        return session_title

    def show_camera_configuration_view(self):
        clear_layout(self._layout)
        camera_configuration_view = CameraConfiguration()
        self._layout.addWidget(camera_configuration_view)

    def connect_to_cameras(self):
        clear_layout(self._layout)
        found_cameras_response = get_or_create_cams()
        APP_STATE.available_cameras = [
            this_cam.webcam_id for this_cam in found_cameras_response.cameras_found_list
        ]
        APP_STATE.selected_cameras = APP_STATE.available_cameras
        self._layout.addWidget(CameraStreamGridView())
