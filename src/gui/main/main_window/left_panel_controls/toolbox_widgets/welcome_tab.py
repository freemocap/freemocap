from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QLineEdit,
    QPushButton,
)

from src.config.home_dir import create_default_session_id
from src.gui.icis_conference_main.shared_widgets.primary_button import PrimaryButton
from src.gui.main.app_state.app_state import APP_STATE
from src.gui.main.styled_widgets.page_title import PageTitle


class SelectWorkflowScreen(QWidget):
    def __init__(self):
        super().__init__()

        container_layout = QVBoxLayout()

        self._start_new_session_button = QPushButton("&Start New Session")
        container_layout.addWidget(self._start_new_session_button)

        self._load_previous_session_button = QPushButton(
            "TO DO - &Load Previous Session"
        )
        self._load_previous_session_button.setEnabled(False)
        container_layout.addWidget(self._load_previous_session_button)

        self._import_external_videos = QPushButton("TO DO - &Import External Videos")
        self._import_external_videos.setEnabled(False)
        container_layout.addWidget(self._import_external_videos)

        self.setLayout(container_layout)

    @property
    def start_new_session_button(self):
        return self._start_new_session_button
