from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QLineEdit,
    QFormLayout,
    QPushButton,
)

from src.config.home_dir import create_session_id
from src.gui.main.app_state.app_state import APP_STATE
from src.gui.main.styled_widgets.primary_button import PrimaryButton


class CreateOrLoadNewSessionPanel(QWidget):
    def __init__(self):
        super().__init__()

        central_layout = QVBoxLayout()

        central_layout.addLayout(self._create_new_session_layout())

        self._load_most_recent_session_button = QPushButton(
            "TO DO - Load Most &Recent Session"
        )
        self._load_most_recent_session_button.setEnabled(False)
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
    def submit_button(self):
        return self._submit_button

    def _create_session_input(self):
        session_text_input = QLineEdit()
        session_text_input.setText(create_session_id())
        return session_text_input

    def _create_new_session_layout(self):
        layout = QVBoxLayout()

        session_id_form_layout = QFormLayout()
        self._session_input = self._create_session_input()
        session_id_form_layout.addRow(QLabel("Session Id"), self._session_input)
        layout.addLayout(session_id_form_layout)

        self._submit_button = PrimaryButton("&Start Session")
        self._submit_button.clicked.connect(self._assign_session_id_to_state)
        layout.addWidget(self._submit_button)
        return layout

    def _assign_session_id_to_state(self):
        APP_STATE.session_id = self._session_input.text()
