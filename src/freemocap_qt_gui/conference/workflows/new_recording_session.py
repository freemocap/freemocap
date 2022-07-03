from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, \
    QWidget

from src.config.home_dir import create_session_id


class NewRecordingSession(QWidget):

    def __init__(self):
        super().__init__()

        container = QVBoxLayout()

        session_title = self._create_record_sesion_title()
        container.addWidget(session_title)

        session_id_text_layout = QHBoxLayout()
        session_id_text_layout.addWidget(QLabel("Session Id"))
        session_id_text_layout.addWidget(self._create_session_input())

        container.addLayout(session_id_text_layout)

        self._submit_button = self._create_submit_button()
        container.addWidget(self._submit_button)

        self.setLayout(container)

    @property
    def submit(self):
        return self._submit_button

    def _create_record_sesion_title(self):
        session_title = QLabel("Name your recording session")
        session_title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        return session_title

    def _create_session_input(self):
        session_text_input = QLineEdit()
        session_text_input.setText(create_session_id())
        return session_text_input

    def _create_submit_button(self):
        submit = QPushButton("&Start Session")
        submit.setFixedWidth(100)
        return submit
