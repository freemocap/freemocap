from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, \
    QWidget

from src.config.home_dir import create_session_id
from src.freemocap_qt_gui.conference.shared_widgets.page_title import PageTitle
from src.freemocap_qt_gui.conference.shared_widgets.primary_button import PrimaryButton
from src.freemocap_qt_gui.refactored_gui.state.app_state import APP_STATE


class NewRecordingSession(QWidget):

    def __init__(self):
        super().__init__()

        self._submit_button = PrimaryButton("&Start Session")

        container = QVBoxLayout()

        session_title = self._create_record_sesion_title()
        container.addWidget(session_title)

        session_id_text_layout = QHBoxLayout()
        session_id_text_layout.addWidget(QLabel("Session Id"))
        self._session_input = self._create_session_input()
        session_id_text_layout.addWidget(self._create_session_input())

        container.addLayout(session_id_text_layout)

        container.addLayout(self._create_submit_button_layout())

        self.setLayout(container)

    @property
    def submit(self):
        return self._submit_button

    def _create_record_sesion_title(self):
        session_title = PageTitle("Name Your Recording Session")
        return session_title

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
