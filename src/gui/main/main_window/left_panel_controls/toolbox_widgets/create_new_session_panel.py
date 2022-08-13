from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QLineEdit,
)

from src.config.home_dir import create_session_id
from src.gui.main.app_state.app_state import APP_STATE
from src.gui.main.styled_widgets.primary_button import PrimaryButton


class CreateNewSessionPanel(QWidget):
    def __init__(self):
        super().__init__()

        self._submit_button = PrimaryButton("&Start Session")

        container_layout = QVBoxLayout()

        session_id_text_layout = QHBoxLayout()
        session_id_text_layout.addWidget(QLabel("Session Id"))
        self._session_input = self._create_session_input()
        session_id_text_layout.addWidget(self._create_session_input())

        container_layout.addLayout(session_id_text_layout)
        container_layout.addLayout(self._create_submit_button_layout())

        self.setLayout(container_layout)

    @property
    def submit_button(self):
        return self._submit_button

    def _create_session_input(self):
        session_text_input = QLineEdit()
        session_text_input.setText(create_session_id())
        return session_text_input

    def _create_submit_button_layout(self):
        submit_button_layout = QHBoxLayout()
        self._submit_button.clicked.connect(self._assign_session_id_to_state)
        submit_button_layout.addWidget(self._submit_button)
        return submit_button_layout

    def _assign_session_id_to_state(self):
        APP_STATE.session_id = self._session_input.text()
