from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMainWindow, QMenuBar, QVBoxLayout, QWidget, QCheckBox

from src.gui.main.app import get_qt_app
from src.gui.main.qt_utils.clear_layout import clearLayout
from src.gui.main.state.app_state import APP_STATE
from src.gui.main.workflows.calibration_instructions import CalibrationInstructions
from src.gui.main.workflows.camera_configuration import CameraConfiguration
from src.gui.main.workflows.new_recording_session import NewRecordingSession
from src.gui.main.workflows.record_videos import RecordVideos
from src.gui.main.workflows.show_cams_charuco import ShowCamsCharuco
from src.gui.main.workflows.welcome import Welcome


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("freemocap")
        self.setGeometry(0, 0, 800, 600)
        self._create_menu_bar()
        self.statusBar()
        self._main_layout = self._create_basic_layout()

        self._show_welcome_screen()

    def _create_basic_layout(self):
        main_layout = QVBoxLayout()
        widget = QWidget()
        widget.setLayout(main_layout)
        self.setCentralWidget(widget)
        return main_layout

    def _create_menu_bar(self):
        menubar = self.menuBar()
        menubar.setNativeMenuBar(False)
        self._add_file_menu(menubar)

    def _add_file_menu(self, menubar: QMenuBar):
        exit_action = self._create_exit_action()
        record_action = self._create_new_recording_session_action()
        file_menu = menubar.addMenu("&File")
        file_menu.addAction(record_action)
        file_menu.addAction(exit_action)

    def _create_exit_action(self):
        # src/freemocap_qt_gui/conference/assets/new_recording_session.png
        action = QAction("&Quit", self)
        action.setShortcut("Ctrl+Q")
        action.setStatusTip("Exit application")

        # On triggered, quit the application
        action.triggered.connect(get_qt_app().quit)

        return action

    def _create_new_recording_session_action(self):
        action = QAction("&New Recording Session", self)
        action.setShortcut("Ctrl+N")
        action.setStatusTip("Begin a new recording session")

        # On triggered, quit the application
        action.triggered.connect(self._show_recording_session_screen)
        return action

    # more top-level screens go here
    # this will be refactored later
    def _show_welcome_screen(self):
        clearLayout(self._main_layout)
        screen = Welcome()
        self._main_layout.addWidget(screen)
        self._main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        screen.new_session.clicked.connect(self._show_recording_session_screen)

    def _show_recording_session_screen(self):
        clearLayout(self._main_layout)
        screen = NewRecordingSession()
        self._main_layout.addWidget(screen)
        self._main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        screen.submit.clicked.connect(self._show_cam_config_screen)

    def _show_cam_config_screen(self):
        clearLayout(self._main_layout)
        screen = CameraConfiguration()
        self._main_layout.addWidget(screen)
        self._main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        # screen.config_accepted.clicked.connect(self._show_calibration_instructions_screen)
        if APP_STATE.use_previous_calibration:
            screen.config_accepted.clicked.connect(self._show_record_videos_screen)
        else:
            screen.config_accepted.clicked.connect(self._show_calibration_screen)

    def _show_calibration_instructions_screen(self):
        clearLayout(self._main_layout)
        screen = CalibrationInstructions()
        self._main_layout.addWidget(screen)
        self._main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        screen.continue_button.clicked.connect(self._show_calibration_screen)

    def _show_calibration_screen(self):
        clearLayout(self._main_layout)
        screen = ShowCamsCharuco()
        self._main_layout.addWidget(screen)
        self._main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        screen.continue_button.clicked.connect(self._show_record_videos_screen)

    def _show_record_videos_screen(self):
        clearLayout(self._main_layout)
        screen = RecordVideos()
        self._main_layout.addWidget(screen)
        self._main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
