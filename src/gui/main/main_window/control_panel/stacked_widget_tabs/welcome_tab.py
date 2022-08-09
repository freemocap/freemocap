from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QLineEdit,
)

from src.config.home_dir import create_session_id
from src.gui.icis_conference_main.shared_widgets.primary_button import PrimaryButton
from src.gui.main.app_state.app_state import APP_STATE
from src.gui.main.styled_widgets.page_title import PageTitle


class WelcomeTab(QWidget):
    def __init__(self):
        super().__init__()

        container_layout = QVBoxLayout()

        self._start_new_session_button = PrimaryButton("&Start New Session")
        container_layout.addWidget(self._start_new_session_button)

        self._load_previous_session_button = PrimaryButton("&Load Previous Session")
        container_layout.addWidget(self._load_previous_session_button)

        self._import_external_videos = PrimaryButton("&Import External Videos")
        container_layout.addWidget(self._import_external_videos)

        self.setLayout(container_layout)
