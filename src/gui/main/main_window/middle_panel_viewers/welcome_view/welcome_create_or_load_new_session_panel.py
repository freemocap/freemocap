import logging

from PyQt6 import QtCore
from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.config.home_dir import create_default_session_id
from src.gui.main.qt_utils.hide_all_in_layout import hide_all_in_layout
from src.gui.main.style_stuff.css_style_sheet import recommended_next_button_style_sheet
from src.gui.main.style_stuff.styled_widgets.page_title import PageTitle

logger = logging.getLogger(__name__)


class WelcomeCreateOrLoadNewSessionPanel(QWidget):
    def __init__(self):
        super().__init__()

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._layout.addStretch()
        self._welcome_to_freemocap_title_widget = self._welcome_to_freemocap_title()
        self._layout.addWidget(self._welcome_to_freemocap_title_widget)

        self._layout.addStretch()

        self._create_new_session_button = QPushButton("Create &New Session (Ctrl+N)")
        self._create_new_session_button.setStyleSheet(
            recommended_next_button_style_sheet
        )
        self._create_new_session_button.clicked.connect(
            self.show_new_session_setup_view
        )
        self._create_new_session_button.setFocus()
        self._layout.addWidget(self._create_new_session_button)

        self._load_most_recent_session_button = QPushButton(
            "Load Most &Recent Session (Ctrl+D)",
        )
        self._load_most_recent_session_button.setEnabled(True)
        self._layout.addWidget(self._load_most_recent_session_button)

        self._load_session_button = QPushButton(
            "Load Session (Ctrl+O)",
        )
        self._load_session_button.setEnabled(True)
        self._layout.addWidget(self._load_session_button)

        self._import_synchronized_videos_button = QPushButton(
            "&Import Synchronized Videos (Ctrl+I)"
        )
        self._import_synchronized_videos_button.setEnabled(True)
        self._import_synchronized_videos_button.setToolTip(
            "Import videos that were recorded and synchronized externally. Each video must have the *exact* same number of frames"
        )
        self._import_synchronized_videos_button.clicked.connect(
            self.show_import_videos_view
        )
        self._layout.addWidget(self._import_synchronized_videos_button)

        send_pings_label = QLabel(
            "(being able to show that people are using this thing will help us get funding for this project :D )"
        )
        send_pings_label.setWordWrap(True)
        self._send_pings_checkbox = QCheckBox(
            "Send ping to devs to let us know when you make a new session"
        )
        self._send_pings_checkbox.setChecked(True)
        self._layout.addWidget(self._send_pings_checkbox)
        self._layout.addWidget(send_pings_label)

        self._layout.addStretch()

        # show this if user selects 'new session' button
        self._session_id_form_layout = self._create_get_session_id_form_layout()
        self._auto_detect_cameras_checkbox = QCheckBox("Automatically detect cameras")
        self._auto_detect_cameras_checkbox.setChecked(True)

        self._auto_connect_to_cameras_checkbox = QCheckBox(
            "Automatically connect to cameras"
        )
        self._auto_connect_to_cameras_checkbox.setChecked(True)

        self._start_session_button = QPushButton("Start Session \U00002728")
        self._start_session_button.setStyleSheet(recommended_next_button_style_sheet)

        # show this if user selects 'import videos' button
        self._synchronize_videos_checkbox = QCheckBox(
            "TODO - Synchronized videos using audio channels"
        )
        self._synchronize_videos_checkbox.setChecked(False)
        self._synchronize_videos_checkbox.setEnabled(False)

        self._launch_synchronized_videos_selection_dialog_button = QPushButton(
            "Select set of synchronized videos..."
        )
        self._launch_synchronized_videos_selection_dialog_button.setStyleSheet(
            recommended_next_button_style_sheet
        )

    @property
    def create_new_session_button(self):
        return self._create_new_session_button

    @property
    def start_session_button(self):
        return self._start_session_button

    @property
    def load_most_recent_session_button(self):
        return self._load_most_recent_session_button

    @property
    def load_session_button(self):
        return self._load_session_button

    @property
    def send_pings_checkbox(self):
        return self._send_pings_checkbox

    @property
    def session_id_input_string(self):
        return self._session_input.text()

    @property
    def auto_detect_cameras_checkbox(self):
        return self._auto_detect_cameras_checkbox

    @property
    def auto_connect_to_cameras_checkbox(self):
        return self._auto_connect_to_cameras_checkbox

    @property
    def synchronized_videos_selection_dialog_button(self):
        return self._launch_synchronized_videos_selection_dialog_button

    def _welcome_to_freemocap_title(self):
        # TO DO - this shouldn't be part of the `camera_view_panel` - it should be its own thing that gets swapped out on session start
        logger.info("Creating `welcome to freemocap` widget")
        welcome_widget = QWidget()
        layout = QVBoxLayout()
        welcome_widget.setLayout(layout)

        session_title_widget = PageTitle(
            "Welcome  to  FreeMoCap! \n  \U00002728 \U0001F480 \U00002728 "
        )
        layout.addWidget(session_title_widget, QtCore.Qt.AlignCenter)

        alpha_version_text_str = "This is an *early* version of the `alpha` version of this software, so like - Manage your Expectations lol "
        layout.addWidget(QLabel(alpha_version_text_str), QtCore.Qt.AlignCenter)

        return welcome_widget

    def _create_session_id_input(self):
        session_text_input = QLineEdit()
        session_text_input.setText(create_default_session_id())
        return session_text_input

    def _create_get_session_id_form_layout(self):
        session_id_form_layout = QFormLayout()
        self._session_input = self._create_session_id_input()
        session_id_form_layout.addRow(QLabel("Session Id"), self._session_input)
        return session_id_form_layout

    def show_new_session_setup_view(self):
        hide_all_in_layout(self._layout)
        self._layout.addStretch()
        self._layout.addLayout(self._session_id_form_layout)

        self._layout.addWidget(self._auto_detect_cameras_checkbox)

        self._layout.addWidget(self._auto_connect_to_cameras_checkbox)
        self._layout.addWidget(self._start_session_button)
        self._start_session_button.setFocus()
        self._layout.addStretch()

    def show_import_videos_view(self):
        hide_all_in_layout(self._layout)
        self._layout.addStretch()
        self._layout.addWidget(
            QLabel("Create a session folder with external recorded/synchronized videos")
        )
        self._layout.addLayout(self._session_id_form_layout)

        self._layout.addWidget(self._synchronize_videos_checkbox)
        self._layout.addWidget(self._launch_synchronized_videos_selection_dialog_button)
        self._launch_synchronized_videos_selection_dialog_button.setFocus()
        self._layout.addStretch()
