import logging

from PyQt6 import QtCore
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QFormLayout,
    QPushButton,
    QCheckBox,
)

from src.config.home_dir import create_default_session_id
from src.gui.main.styled_widgets.page_title import PageTitle
from src.gui.main.styled_widgets.primary_button import PrimaryButton

logger = logging.getLogger(__name__)


class WelcomeCreateOrLoadNewSessionPanel(QWidget):
    def __init__(self):
        super().__init__()

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._layout.addStretch()
        self._welcome_to_freemocap_title_widget = self._welcome_to_freemocap_title()
        self._layout.addWidget(self._welcome_to_freemocap_title_widget)

        self._layout.addStretch()

        self._layout.addLayout(self._create_get_session_id_form_layout())

        self._start_new_session_button = PrimaryButton("&Start New Session (Ctrl+N)")
        self._layout.addWidget(self._start_new_session_button)

        self._load_most_recent_session_button = QPushButton(
            "Load Most &Recent Session (Ctrl+D)",
        )
        self._load_most_recent_session_button.setEnabled(True)
        self._layout.addWidget(self._load_most_recent_session_button)

        self._load_session_button = QPushButton(
            "Load Session (Ctrl+O)",
        )
        self._load_session_button.setEnabled(True)
        self._layout.addWidget(self._load_session_button)

        self._import_external_videos_button = QPushButton("Import External &Videos")
        self._import_external_videos_button.setEnabled(True)
        self._layout.addWidget(self._import_external_videos_button)

        self._layout.addStretch()

        self._send_pings_checkbox = QCheckBox(
            "Send ping to devs to let us know when you make a new session because that will help us get funding for this project :D "
        )
        self._send_pings_checkbox.setChecked(True)
        self._layout.addWidget(self._send_pings_checkbox)

    @property
    def start_new_session_button(self):
        return self._start_new_session_button

    @property
    def load_most_recent_session_button(self):
        return self._load_most_recent_session_button

    @property
    def load_session_button(self):
        return self._load_session_button

    @property
    def import_external_videos_button(self):
        return self._import_external_videos_button

    @property
    def send_pings_checkbox(self):
        return self._send_pings_checkbox

    @property
    def session_id_input_string(self):
        return self._session_input.text()

    def _welcome_to_freemocap_title(self):
        # TO DO - this shouldn't be part of the `camera_view_panel` - it should be its own thing that gets swapped out on session start
        logger.info("Creating `welcome to freemocap` widget")
        welcome_widget = QWidget()
        layout = QVBoxLayout()
        welcome_widget.setLayout(layout)

        session_title_widget = PageTitle(
            "Welcome  to  FreeMoCap! \n  \U00002728 \U0001F480 \U00002728 "
        )
        layout.addWidget(session_title_widget, QtCore.Qt.AlignCenter)

        alpha_version_text_str = "This is an *early* version of the `alpha` version of this software, so like - Manage your Expectations lol "
        layout.addWidget(QLabel(alpha_version_text_str), QtCore.Qt.AlignCenter)

        return welcome_widget

    def _create_session_id_input(self):
        session_text_input = QLineEdit()
        session_text_input.setText(create_default_session_id())
        return session_text_input

    def _create_get_session_id_form_layout(self):
        session_id_form_layout = QFormLayout()
        self._session_input = self._create_session_id_input()
        session_id_form_layout.addRow(QLabel("Session Id"), self._session_input)
        return session_id_form_layout
