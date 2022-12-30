import logging
from pathlib import Path
from typing import List

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.gui.main.custom_widgets.video_player_widget import VideoPlayerWidget
from src.gui.main.qt_utils.clear_layout import clear_layout

logger = logging.getLogger(__name__)


class VideoPlaybackGridView(QWidget):
    def __init__(self):
        super().__init__()

        self._layout = QHBoxLayout()
        self.setLayout(self._layout)

        self._dictionary_of_video_widgets = {}

        self._dictionary_of_video_image_update_callbacks = {}

    @property
    def dictionary_video_image_update_callbacks(self):
        return self._dictionary_of_video_image_update_callbacks

    def create_video_widgets(
        self,
        list_of_video_paths: List,
    ):
        clear_layout(self._layout)
        logger.info("Creating video widgets...")

        for video_path in list_of_video_paths:
            video_name = Path(video_path).stem
            video_widget = VideoPlayerWidget()
            self._dictionary_of_video_widgets[video_name] = video_widget

            video_layout = QVBoxLayout()
            video_layout.addWidget(QLabel(f"{video_name}"))
            video_layout.addWidget(video_widget)
            self._layout.addLayout(video_layout)

            self._dictionary_of_video_image_update_callbacks[
                video_name
            ] = video_widget.update_image
