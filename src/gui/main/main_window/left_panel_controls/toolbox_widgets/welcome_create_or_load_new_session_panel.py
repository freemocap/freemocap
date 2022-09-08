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
        self._layout.addLayout(self._create_new_session_layout())

        self._load_most_recent_session_button = QPushButton(
            "Load Most &Recent Session",
        )
        self._load_most_recent_session_button.setEnabled(True)
        self._layout.addWidget(self._load_most_recent_session_button)

        self._load_session_button = QPushButton(
            "Load Session",
        )
        self._load_session_button.setEnabled(True)
        self._layout.addWidget(self._load_session_button)

        self._import_external_videos_button = QPushButton(
            "TO DO - Import External &Videos"
        )
        self._import_external_videos_button.setEnabled(False)
        self._layout.addWidget(self._import_external_videos_button)

        self._layout.addStretch()

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

    def _create_session_input(self):
        session_text_input = QLineEdit()
        session_text_input.setText(create_default_session_id())
        return session_text_input

    def _create_new_session_layout(self):
        layout = QVBoxLayout()

        session_id_form_layout = QFormLayout()
        self._session_input = self._create_session_input()
        session_id_form_layout.addRow(QLabel("Session Id"), self._session_input)
        layout.addLayout(session_id_form_layout)
        layout.setAlignment(Qt.AlignBottom)

        self._start_new_session_button = PrimaryButton("&Start Session")
        layout.addWidget(self._start_new_session_button)
        return layout
