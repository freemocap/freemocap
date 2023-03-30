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

from freemocap.gui.qt.actions_and_menus.actions import (
    CREATE_NEW_RECORDING_ACTION_NAME,
    LOAD_MOST_RECENT_RECORDING_ACTION_NAME,
    LOAD_RECORDING_ACTION_NAME,
    IMPORT_VIDEOS_ACTION_NAME,
    Actions,
)
from freemocap.system.paths_and_files_names import PATH_TO_FREEMOCAP_LOGO_SVG, SPARKLES_EMOJI_STRING

logger = logging.getLogger(__name__)


class WelcomeScreenButton(QPushButton):
    def __init__(self, text: str, parent: QWidget = None):
        super().__init__(text, parent=parent)
        self.setFixedHeight(50)
        self.setFixedWidth(400)


class HomeWidget(QWidget):
    def __init__(self, actions: Actions, parent: QWidget = None):
        super().__init__(parent=parent)

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self.sizePolicy().setHorizontalStretch(1)
        self.sizePolicy().setVerticalStretch(1)

        self._layout.addStretch(1)

        self._add_freemocap_logo()

        self._welcome_to_freemocap_title_widget = self._welcome_to_freemocap_title()
        self._layout.addWidget(self._welcome_to_freemocap_title_widget)

        self._create_new_session_button = WelcomeScreenButton(
            f"{CREATE_NEW_RECORDING_ACTION_NAME}"
        )
        self._create_new_session_button.clicked.connect(actions.create_new_recording_action.trigger)
        self._layout.addWidget(self._create_new_session_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self._create_new_session_button.setProperty("recommended_next", True)

        self._load_most_recent_session_button = WelcomeScreenButton(
            f"{LOAD_MOST_RECENT_RECORDING_ACTION_NAME}"
        )
        # self._load_most_recent_session_button.clicked.connect(actions.load_most_recent_recording_action.trigger)
        # self._layout.addWidget(self._load_most_recent_session_button, alignment=Qt.AlignmentFlag.AlignCenter)
        #
        self._load_existing_session_button = WelcomeScreenButton(f"{LOAD_RECORDING_ACTION_NAME}")
        self._load_existing_session_button.clicked.connect(actions.load_existing_recording_action.trigger)
        self._layout.addWidget(self._load_existing_session_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self._import_videos_button = WelcomeScreenButton(f"{IMPORT_VIDEOS_ACTION_NAME}")
        self._import_videos_button.clicked.connect(actions.import_videos_action.trigger)
        self._layout.addWidget(self._import_videos_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self._layout.addStretch(1)

        send_pings_string = "Send anonymous usage information"
        self._send_pings_checkbox = QCheckBox(send_pings_string)
        self._send_pings_checkbox.setChecked(True)
        self._layout.addWidget(self._send_pings_checkbox, alignment=Qt.AlignmentFlag.AlignCenter)

        privacy_policy_link_string = '<a href="https://freemocap.readthedocs.io/en/latest/privacy_policy/" style="color: white;">Click here to view our privacy policy</a>'
        self._privacy_policy_link = QLabel(privacy_policy_link_string)
        self._privacy_policy_link.setOpenExternalLinks(True)
        self._layout.addWidget(self._privacy_policy_link, alignment=Qt.AlignmentFlag.AlignCenter)

        self.style().polish(self)

    def _welcome_to_freemocap_title(self):
        # TO DO - this shouldn't be part of the `camera_view_panel` - it should be its own thing that gets swapped out on session start
        logger.info("Creating `welcome to freemocap` layout")

        session_title_label = QLabel("Welcome  to  FreeMoCap!")
        session_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        session_title_label.setStyleSheet("font-size: 54px;")

        return session_title_label

    def _add_freemocap_logo(self):
        freemocap_logo_label = QLabel(self)
        freemocap_logo_label.sizePolicy().setHorizontalStretch(1)
        freemocap_logo_label.sizePolicy().setVerticalStretch(1)
        self._layout.addWidget(freemocap_logo_label)
        freemocap_logo_pixmap = QPixmap(PATH_TO_FREEMOCAP_LOGO_SVG)
        freemocap_logo_pixmap = freemocap_logo_pixmap.scaledToWidth(200)
        freemocap_logo_label.setPixmap(freemocap_logo_pixmap)
        freemocap_logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
