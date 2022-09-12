from typing import List

import numpy as np
from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QWidget,
)

from src.gui.main.main_window.left_panel_controls.toolbox_widgets.welcome_create_or_load_new_session_panel import (
    WelcomeCreateOrLoadNewSessionPanel,
)

from src.gui.main.main_window.middle_panel_viewers.camera_stream_grid_view import (
    CameraStreamGridView,
)
from src.gui.main.main_window.middle_panel_viewers.session_playback_view.session_playback_view import (
    SessionPlaybackView,
)
from src.gui.main.main_window.middle_panel_viewers.session_playback_view.video_playback_grid_view import (
    VideoPlaybackGridView,
)
from src.gui.main.visualize_session.gl_3d_view_port import Gl3dViewPort

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
        self._camera_stream_grid_view.hide()

        self._layout.addWidget(self._camera_stream_grid_view)

        self._session_playback_view = SessionPlaybackView()
        self._session_playback_view.hide()

        self._layout.addWidget(self._session_playback_view)

    @property
    def frame(self):
        return self._frame

    @property
    def welcome_create_or_load_session_panel(self):
        return self._welcome_create_or_load_session_panel

    @property
    def camera_stream_grid_view(self):
        return self._camera_stream_grid_view

    @property
    def session_playback_view(self):
        return self._session_playback_view

    @property
    def dictionary_of_video_image_update_callbacks(self):
        return self._session_playback_view.dictionary_of_video_image_update_callbacks

    def show_camera_streams(self):
        logger.info("Showing camera stream grid view")
        self._welcome_create_or_load_session_panel.hide()
        self._camera_stream_grid_view.show()

    def show_session_playback_view(
        self, list_of_video_paths: List, mediapipe3d_trackedPoint_xyz: np.ndarray
    ):
        self._session_playback_view.initialize_video_playback_grid(
            list_of_video_paths=list_of_video_paths,
        )
        self._session_playback_view.initialize_skeleton_view(
            mediapipe3d_trackedPoint_xyz=mediapipe3d_trackedPoint_xyz
        )
        self._camera_stream_grid_view.hide()
        self._session_playback_view.show()
