import logging
from typing import List

import numpy as np
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from src.gui.main.main_window.middle_panel_viewers.session_playback_view.video_playback_grid_view import (
    VideoPlaybackGridView,
)
from src.gui.main.visualize_session.gl_3d_view_port import Gl3dViewPort

logger = logging.getLogger(__name__)


class SessionPlaybackView(QWidget):
    def __init__(self):
        super().__init__()

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._video_playback_grid_view = VideoPlaybackGridView()
        self._layout.addWidget(self._video_playback_grid_view)

        self._gl_3d_view_port_widget = Gl3dViewPort()
        self._layout.addWidget(self._gl_3d_view_port_widget)

    @property
    def dictionary_of_video_image_update_callbacks(self):
        return self._video_playback_grid_view.dictionary_video_image_update_callbacks

    @property
    def update_3d_skeleton_callback(self):
        return self._gl_3d_view_port_widget.update_mediapipe3d_skeleton

    def initialize_video_playback_grid(self, list_of_video_paths: List):
        logger.info("Showing video playback grid")
        self._video_playback_grid_view.create_video_widgets(
            list_of_video_paths=list_of_video_paths
        )

    def initialize_skeleton_view(self, mediapipe3d_trackedPoint_xyz: np.ndarray):
        self._gl_3d_view_port_widget.initialize_mediapipe_3d_skeleton(
            mediapipe3d_trackedPoint_xyz=mediapipe3d_trackedPoint_xyz
        )
