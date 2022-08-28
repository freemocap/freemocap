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
from src.gui.main.styled_widgets.primary_button import PrimaryButton


class CreateOrLoadNewSessionPanel(QWidget):
    def __init__(self):
        super().__init__()

        central_layout = QVBoxLayout()

        central_layout.addLayout(self._create_new_session_layout())

        self._load_most_recent_session_button = QPushButton(
            "Load Most &Recent Session",
        )
        self._load_most_recent_session_button.setEnabled(True)
        central_layout.addWidget(self._load_most_recent_session_button)

        self._load_session_button = QPushButton("TO DO - &Load Session")
        self._load_session_button.setEnabled(False)
        central_layout.addWidget(self._load_session_button)

        self._import_external_videos_button = QPushButton(
            "TO DO - Import External &Videos"
        )
        self._import_external_videos_button.setEnabled(False)
        central_layout.addWidget(self._import_external_videos_button)

        self.setLayout(central_layout)

    @property
    def start_new_session_button(self):
        return self._start_new_session_button

    @property
    def load_most_recent_session_button(self):
        return self._load_most_recent_session_button

    @property
    def session_id_input_string(self):
        return self._session_input.text()

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
