from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMainWindow, QMenuBar, QVBoxLayout, \
    QWidget

from src.freemocap_qt_gui.conference.app import get_qt_app
from src.freemocap_qt_gui.conference.qt_utils.clear_layout import clearLayout
from src.freemocap_qt_gui.conference.workflows.camera_configuration import CameraConfiguration
from src.freemocap_qt_gui.conference.workflows.new_recording_session import \
    NewRecordingSession


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('freemocap')
        self.setGeometry(0, 0, 800, 600)
        self._create_menu_bar()
        self.statusBar()
        self._main_layout = self._create_basic_layout()

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
        file_menu = menubar.addMenu('&File')
        file_menu.addAction(record_action)
        file_menu.addAction(exit_action)

    def _create_exit_action(self):
        # src/freemocap_qt_gui/conference/assets/new_recording_session.png
        action = QAction('&Quit', self)
        action.setShortcut('Ctrl+Q')
        action.setStatusTip('Exit application')

        # On triggered, quit the application
        action.triggered.connect(get_qt_app().quit)

        return action

    def _create_new_recording_session_action(self):
        action = QAction('&New Recording Session', self)
        action.setShortcut('Ctrl+N')
        action.setStatusTip('Begin a new recording session')

        # On triggered, quit the application
        action.triggered.connect(self._show_recording_session_screen)
        return action

    def _show_recording_session_screen(self):
        clearLayout(self._main_layout)
        widg = NewRecordingSession()
        self._main_layout.addWidget(widg)
        self._main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        widg.submit.clicked.connect(self._show_cam_config_screen)

    def _show_cam_config_screen(self):
        clearLayout(self._main_layout)
        screen = CameraConfiguration()
        self._main_layout.addWidget(screen)
        self._main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
