import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from freemocap.configuration.paths_and_files_names import PATH_TO_FREEMOCAP_LOGO_SVG

logger = logging.getLogger(__name__)


class WelcomeCreateOrLoadNewSessionPanel(QWidget):
    def __init__(self):
        super().__init__()

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._add_freemocap_logo()

        self._welcome_to_freemocap_title_widget = self._welcome_to_freemocap_title()
        self._layout.addWidget(self._welcome_to_freemocap_title_widget)

        self._quick_start_button = QPushButton("Quick Start")
        self._quick_start_button.setStyleSheet("font-size: 24px;")
        self._layout.addWidget(self._quick_start_button)

        send_pings_label = QLabel(
            "(being able to show that people are using this thing will help us get funding for this project :D )"
        )
        send_pings_label.setWordWrap(True)
        self._send_pings_checkbox = QCheckBox("Send ping to devs to let us know when you make a new session")
        self._send_pings_checkbox.setChecked(True)
        self._layout.addWidget(self._send_pings_checkbox)
        self._layout.addWidget(send_pings_label)

        self._layout.addStretch()

    @property
    def quick_start_button(self):
        return self._quick_start_button

    def _welcome_to_freemocap_title(self):
        # TO DO - this shouldn't be part of the `camera_view_panel` - it should be its own thing that gets swapped out on session start
        logger.info("Creating `welcome to freemocap` layout")

        session_title_label = QLabel("Welcome  to  FreeMoCap!")
        session_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        session_title_label.setStyleSheet("font-size: 54px;")

        return session_title_label

    def _add_freemocap_logo(self):
        freemocap_logo_label = QLabel(self)
        self._layout.addWidget(freemocap_logo_label)
        freemocap_logo_pixmap = QPixmap(PATH_TO_FREEMOCAP_LOGO_SVG)
        freemocap_logo_pixmap = freemocap_logo_pixmap.scaledToWidth(300)
        freemocap_logo_label.setPixmap(freemocap_logo_pixmap)
        freemocap_logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
