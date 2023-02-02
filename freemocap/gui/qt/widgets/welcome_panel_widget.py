import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from freemocap.system.paths_and_files_names import PATH_TO_FREEMOCAP_LOGO_SVG
from freemocap.gui.qt.actions_and_menu_bar.actions import (
    CREATE_NEW_RECORDING_ACTION_NAME,
    LOAD_MOST_RECENT_RECORDING_ACTION_NAME,
    LOAD_EXISTING_RECORDING_ACTION_NAME,
    IMPORT_VIDEOS_ACTION_NAME,
    REBOOT_GUI_ACTION_NAME,
    EXIT_ACTION_NAME,
    Actions,
)

logger = logging.getLogger(__name__)


class WelcomeToFreemocapPanel(QWidget):
    def __init__(self, actions: Actions, parent: QWidget = None):
        super().__init__(parent=parent)

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._add_freemocap_logo()

        self._welcome_to_freemocap_title_widget = self._welcome_to_freemocap_title()
        self._layout.addWidget(self._welcome_to_freemocap_title_widget)

        self._create_new_session_button = QPushButton(f"{CREATE_NEW_RECORDING_ACTION_NAME} (Ctrl+N)")
        self._create_new_session_button.clicked.connect(actions.create_new_recording_action.trigger)
        self._layout.addWidget(self._create_new_session_button)

        self._load_most_recent_session_button = QPushButton(f"{LOAD_MOST_RECENT_RECORDING_ACTION_NAME} (Ctrl+D)")
        self._load_most_recent_session_button.clicked.connect(actions.load_most_recent_recording_action.trigger)
        self._layout.addWidget(self._load_most_recent_session_button)

        self._load_existing_session_button = QPushButton(f"{LOAD_EXISTING_RECORDING_ACTION_NAME} (Ctrl+O)")
        self._load_existing_session_button.clicked.connect(actions.load_most_recent_recording_action.trigger)
        self._layout.addWidget(self._load_existing_session_button)

        self._import_videos_button = QPushButton(f"{IMPORT_VIDEOS_ACTION_NAME} (Ctrl+I)")
        self._import_videos_button.clicked.connect(actions.import_videos_action.trigger)
        self._layout.addWidget(self._import_videos_button)

        self._reboot_gui_button = QPushButton(f"{REBOOT_GUI_ACTION_NAME} (Ctrl+R)")
        self._reboot_gui_button.clicked.connect(actions.reboot_gui_action.trigger)
        self._layout.addWidget(self._reboot_gui_button)

        self._exit_button = QPushButton(f"{EXIT_ACTION_NAME} (Ctrl+Q)")
        self._exit_button.clicked.connect(actions.exit_action.trigger)
        self._layout.addWidget(self._exit_button)

        send_pings_label = QLabel(
            "(being able to show that people are using this thing will help us get funding for this project :D )"
        )
        send_pings_label.setWordWrap(True)
        self._send_pings_checkbox = QCheckBox("Send ping to devs to let us know when you make a new session")
        self._send_pings_checkbox.setChecked(True)
        self._layout.addWidget(self._send_pings_checkbox)
        self._layout.addWidget(send_pings_label)

        self._layout.addStretch()

    def _welcome_to_freemocap_title(self):
        # TO DO - this shouldn't be part of the `camera_view_panel` - it should be its own thing that gets swapped out on session start
        logger.info("Creating `welcome to freemocap` layout")

        session_title_label = QLabel("Welcome  to  FreeMoCap!")
        session_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        session_title_label.setStyleSheet("font-size: 54px;")

        return session_title_label

    def _add_freemocap_logo(self):
        freemocap_logo_label = QLabel(self)
        self._layout.addWidget(freemocap_logo_label)
        freemocap_logo_pixmap = QPixmap(PATH_TO_FREEMOCAP_LOGO_SVG)
        freemocap_logo_pixmap = freemocap_logo_pixmap.scaledToWidth(300)
        freemocap_logo_label.setPixmap(freemocap_logo_pixmap)
        freemocap_logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
