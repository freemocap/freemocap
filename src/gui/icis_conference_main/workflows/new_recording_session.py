from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QCheckBox,
)

from src.config.home_dir import create_default_session_id
from src.gui.icis_conference_main.shared_widgets.page_title import PageTitle
from src.gui.icis_conference_main.shared_widgets.primary_button import PrimaryButton
from src.gui.icis_conference_main.state.app_state import APP_STATE


class NewRecordingSession(QWidget):
    def __init__(self):
        super().__init__()

        self._submit_button = PrimaryButton("&Start Session")
        self._use_previous_calibration_checkbox = (
            self._create_use_previous_calibration_checkbox()
        )

        container = QVBoxLayout()

        session_title = self._create_record_sesion_title()
        container.addWidget(session_title)

        session_id_text_layout = QHBoxLayout()
        session_id_text_layout.addWidget(QLabel("Session Id"))
        self._session_input = self._create_session_input()
        session_id_text_layout.addWidget(self._create_session_input())

        container.addLayout(session_id_text_layout)
        container.addWidget(self._use_previous_calibration_checkbox)
        container.addLayout(self._create_submit_button_layout())

        self.setLayout(container)

    @property
    def submit(self):
        return self._submit_button

    def _create_use_previous_calibration_checkbox(self):
        previous_calibration_checkbox = QCheckBox("Use Previous Calibration")
        previous_calibration_checkbox.setChecked(False)
        previous_calibration_checkbox.stateChanged.connect(
            self._use_previous_calibration_changed
        )
        return previous_calibration_checkbox

    def _create_record_sesion_title(self):
        session_title = PageTitle(
            "welcome \n to \n freemocap! \n  \U00002728 \U0001F480 \U00002728 "
        )
        return session_title

    def _create_session_input(self):
        session_text_input = QLineEdit()
        session_text_input.setText(create_default_session_id())
        return session_text_input

    def _create_submit_button_layout(self):
        submit_button_layout = QHBoxLayout()
        self._submit_button.clicked.connect(self._assign_session_id_to_state)
        submit_button_layout.addWidget(self._submit_button)
        return submit_button_layout

    def _assign_session_id_to_state(self):
        APP_STATE.session_id = self._session_input.text()

    def _use_previous_calibration_changed(self):
        APP_STATE.use_previous_calibration_box_is_checked = (
            self._use_previous_calibration_checkbox.isChecked()
        )
