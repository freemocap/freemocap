import logging
from typing import Union

import requests
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
)
from packaging import version

import freemocap
from freemocap.gui.qt.actions_and_menus.actions import (
    CREATE_NEW_RECORDING_ACTION_NAME,
    LOAD_MOST_RECENT_RECORDING_ACTION_NAME,
    LOAD_RECORDING_ACTION_NAME,
    IMPORT_VIDEOS_ACTION_NAME,
    Actions,
)
from freemocap.gui.qt.utilities.save_and_load_gui_state import GuiState, save_gui_state

from freemocap.system.paths_and_filenames.file_and_folder_names import PATH_TO_FREEMOCAP_LOGO_SVG
from freemocap.system.paths_and_filenames.path_getters import get_gui_state_json_path

logger = logging.getLogger(__name__)


class WelcomeScreenButton(QPushButton):
    def __init__(self, text: str, parent: QWidget = None):
        super().__init__(text, parent=parent)
        self.setFixedHeight(50)
        self.setFixedWidth(400)


class HomeWidget(QWidget):
    def __init__(self, actions: Actions, gui_state: GuiState, parent: QWidget = None):
        super().__init__(parent=parent)

        self.gui_state = gui_state

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self.sizePolicy().setHorizontalStretch(1)
        self.sizePolicy().setVerticalStretch(1)

        self._layout.addStretch(1)

        self._add_freemocap_logo()

        self._welcome_to_freemocap_title_widget = self._welcome_to_freemocap_title()
        self._layout.addWidget(self._welcome_to_freemocap_title_widget)

        self._create_new_session_button = WelcomeScreenButton(f"{CREATE_NEW_RECORDING_ACTION_NAME}")
        self._create_new_session_button.clicked.connect(actions.create_new_recording_action.trigger)
        self._layout.addWidget(self._create_new_session_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self._create_new_session_button.setProperty("recommended_next", True)

        self._load_most_recent_session_button = WelcomeScreenButton(f"{LOAD_MOST_RECENT_RECORDING_ACTION_NAME}")
        # self._load_most_recent_session_button.clicked.connect(actions.load_most_recent_recording_action.trigger)
        # self._layout.addWidget(self._load_most_recent_session_button, alignment=Qt.AlignmentFlag.AlignCenter)
        #
        self._load_existing_session_button = WelcomeScreenButton(f"{LOAD_RECORDING_ACTION_NAME}")
        self._load_existing_session_button.clicked.connect(actions.load_existing_recording_action.trigger)
        self._layout.addWidget(self._load_existing_session_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self._import_videos_button = WelcomeScreenButton(f"{IMPORT_VIDEOS_ACTION_NAME}")
        self._import_videos_button.clicked.connect(actions.import_videos_action.trigger)
        self._layout.addWidget(self._import_videos_button, alignment=Qt.AlignmentFlag.AlignCenter)

        # self._layout.addStretch(1)

        self._create_user_info_consent_checkbox()

        self._add_text_links()
        self._make_version_label()

        self.style().polish(self)

    def _make_version_label(self):
        hbox = QHBoxLayout()
        self._layout.addLayout(hbox)
        version_label_string = f'source:<a href="https://github.com/freemocap/freemocap" style="color: #777777;"> {freemocap.__version__}</a>'
        latest_version = self.check_for_latest_version()
        if latest_version is not None:
            latest_version = latest_version.split("rc")[0]
        current_version = freemocap.__version__.strip("v").split("-")[0]

        if latest_version is None:
            version_label_string += " (X)"
            tooltip_string = " (`new version check` failed!)"
        elif latest_version != current_version:
            version_label_string += " (update available!)"
            tooltip_string = (
                f"New version {latest_version} available!\n"
                f" upgrade to latest version by entering the command \n\n"
                f" ```\npip install freemocap --upgrade --pre\n``` "
                f"\n\ninto the terminal you used to launch this program (with your `(freemocap-env)` environment activated)"
            )
        else:
            tooltip_string = f"Your version of freemocap ({freemocap.__version__}) is up to date! (latest: {self.check_for_latest_version()})"
        version_label = QLabel(version_label_string)
        version_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        version_label.setStyleSheet("font-size: 12px;color: #777777")
        version_label.setOpenExternalLinks(True)
        version_label.setToolTip(tooltip_string)

        hbox.addWidget(version_label)

    def check_for_latest_version(self) -> Union[str, None]:
        try:
            response = requests.get(f"https://pypi.org/pypi/{freemocap.__package_name__}/json", timeout=(5, 60))
        except requests.RequestException:
            logger.error(f"Failed to check for latest version of {freemocap.__package_name__}")
            return None

        versions = response.json()["releases"].keys()

        pre_releases = [v for v in versions if "a" in v or "b" in v or "rc" in v]
        if pre_releases:
            pre_releases.sort(key=version.parse)

        versions = list(versions)
        versions.sort(key=version.parse)
        all_versions = pre_releases + versions
        all_versions.sort(key=version.parse)

        return all_versions[-1] if all_versions else None

    def _add_text_links(self):
        hbox = QHBoxLayout()
        self._layout.addLayout(hbox)
        hbox.addStretch(1)
        privacy_policy_link_string = '<a href="https://freemocap.readthedocs.io/en/latest/community/privacy_policy/" style="color: #333333;">privacy policy</a>'
        privacy_policy_link_label = QLabel(privacy_policy_link_string)
        privacy_policy_link_label.setOpenExternalLinks(True)
        hbox.addWidget(privacy_policy_link_label)
        docs_string = '<a href="https://freemocap.readthedocs.io/en/latest/" style="color: #333333;">docs</a>'
        docs_string = QLabel(docs_string)
        docs_string.setOpenExternalLinks(True)
        hbox.addWidget(docs_string, alignment=Qt.AlignmentFlag.AlignCenter)
        feedback_string = '<a href="https://forms.gle/AguGxQAJGXxaJbXdA" style="color: #333333;">feedback</a>'
        feedback_string = QLabel(feedback_string)
        feedback_string.setOpenExternalLinks(True)
        hbox.addWidget(feedback_string, alignment=Qt.AlignmentFlag.AlignRight)
        donate_string = '<a href="https://freemocap.org/about-us.html#donate" style="color: #333333;">donate &lt;3</a>'
        donate_string = QLabel(donate_string)
        donate_string.setOpenExternalLinks(True)
        hbox.addWidget(donate_string, alignment=Qt.AlignmentFlag.AlignRight)

        hbox.addStretch(1)

    def _create_user_info_consent_checkbox(self):
        hbox = QHBoxLayout()
        self._layout.addLayout(hbox)
        hbox.addStretch(1)
        self._send_pings_checkbox = QCheckBox("Send anonymous usage information")
        self._send_pings_checkbox.setChecked(self.gui_state.send_user_pings)
        self._send_pings_checkbox.stateChanged.connect(self._on_send_pings_checkbox_changed)
        hbox.addWidget(self._send_pings_checkbox)

        hbox.addStretch(1)

    @property
    def consent_to_send_usage_information(self):
        return self._send_pings_checkbox.isChecked()

    def _on_send_pings_checkbox_changed(self):
        self.gui_state.send_user_pings = self._send_pings_checkbox.isChecked()
        save_gui_state(gui_state=self.gui_state, file_pathstring=get_gui_state_json_path())

    def _welcome_to_freemocap_title(self):
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
