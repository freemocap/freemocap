from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QMainWindow,
    QMenuBar,
    QWidget,
    QHBoxLayout,
    QGridLayout,
    QVBoxLayout,
    QLabel,
    QFrame,
    QSplitter,
)

from src.gui.icis_conference_main.icis_conference_app import get_qt_app
from src.gui.icis_conference_main.qt_utils.clear_layout import clearLayout
from src.gui.icis_conference_main.qt_widgets.jupyter_console_widget import (
    JupyterConsoleWidget,
)
from src.gui.icis_conference_main.state.app_state import APP_STATE
from src.gui.icis_conference_main.workflows.calibration_instructions import (
    CalibrationInstructions,
)
from src.gui.icis_conference_main.workflows.camera_configuration import (
    CameraConfiguration,
)
from src.gui.icis_conference_main.workflows.new_recording_session import (
    NewRecordingSession,
)
from src.gui.icis_conference_main.workflows.record_videos import RecordVideos
from src.gui.icis_conference_main.workflows.show_cams_charuco import ShowCamsCharuco
from src.gui.icis_conference_main.workflows.welcome import Welcome


class SlopMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("freemocap")
        self._main_window_width = int(1920 * 0.8)
        self._main_window_height = int(1080 * 0.8)
        self.setGeometry(0, 0, self._main_window_width, self._main_window_height)
        self._create_menu_bar()
        self.statusBar()
        self._main_layout = self._create_basic_layout()

        self._control_panel_layout = self._create_control_panel_layout()
        self._camera_view_panel_layout = self._create_camera_view_panel_layout()

        self._jupyter_console_widget = self._create_jupyter_console_widget()
        self._console_panel_layout = self._create_console_panel_layout(
            self._jupyter_console_widget
        )

        self._jupyter_console_widget.print("Hello there!")
        self._show_welcome_view()

    def _create_basic_layout(self):
        main_layout = QHBoxLayout()
        widget = QWidget()
        widget.setLayout(main_layout)

        self.setCentralWidget(widget)
        return main_layout

    def _create_control_panel_layout(self):
        control_panel_frame = QFrame()
        control_panel_frame.setFixedWidth(self._main_window_width * 0.2)
        control_panel_frame.setFrameShape(QFrame.Shape.StyledPanel)
        control_panel_layout = QVBoxLayout()
        control_panel_frame.setLayout(control_panel_layout)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget((control_panel_frame))
        self._main_layout.addWidget(splitter)
        return control_panel_layout

    def _create_camera_view_panel_layout(self):
        camera_view_panel_frame = QFrame()
        camera_view_panel_frame.setFixedWidth(self._main_window_width * 0.4)
        camera_view_panel_frame.setFrameShape(QFrame.Shape.StyledPanel)
        camera_view_panel_layout = QVBoxLayout()
        camera_view_panel_frame.setLayout(camera_view_panel_layout)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget((camera_view_panel_frame))
        self._main_layout.addWidget(splitter)
        return camera_view_panel_layout

    def _create_console_panel_layout(self, jupyter_console_widget):
        console_panel_frame = QFrame()
        console_panel_frame.setFixedWidth(self._main_window_width * 0.4)
        console_panel_frame.setFrameShape(QFrame.Shape.StyledPanel)
        console_panel_layout = QVBoxLayout()
        console_panel_layout.addWidget(jupyter_console_widget)
        console_panel_frame.setLayout(console_panel_layout)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget((console_panel_frame))
        self._main_layout.addWidget(splitter)
        return console_panel_layout

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
        # action.triggered.connect(self._show_welcome_view)
        action.triggered.connect(self._show_cam_config_screen)
        return action

    def _create_jupyter_console_widget(self):
        # create jupyter console widget
        jupyter_console_widget = JupyterConsoleWidget()
        get_qt_app().aboutToQuit.connect(jupyter_console_widget.shutdown_kernel)

        return jupyter_console_widget

    # # more top-level screens go here
    # # this will be refactored later
    # def _show_welcome_screen(self):
    #     clear_layout(self._main_layout)
    #     screen = Welcome()
    #     self._main_layout.addWidget(screen)
    #     self._main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    #     screen.new_session.clicked.connect(self._show_welcome_view)

    def _show_welcome_view(self):
        clearLayout(self._control_panel_layout)
        screen = NewRecordingSession()
        self._control_panel_layout.addWidget(screen)
        # self._main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        # screen.submit.clicked.connect(self._show_cam_config_screen)
        screen.submit.clicked.connect(self._show_cam_config_screen)

    def _show_cam_config_screen(self):
        clearLayout(self._camera_view_panel_layout)
        screen = CameraConfiguration()
        self._camera_view_panel_layout.addWidget(screen)
        # self._main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        # screen.config_accepted.clicked.connect(self._show_calibration_instructions_screen)
        if APP_STATE.use_previous_calibration:
            screen.config_accepted.clicked.connect(self._show_record_videos_screen)
        else:
            screen.config_accepted.clicked.connect(self._show_calibration_screen)

    # def _show_calibration_instructions_screen(self):
    #     clear_layout(self._main_layout)
    #     screen = CalibrationInstructions()
    #     self._main_layout.addWidget(screen)
    #     self._main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    #     screen.continue_button.clicked.connect(self._show_calibration_screen)

    def _show_calibration_screen(self):
        clearLayout(self._main_layout)
        screen = ShowCamsCharuco()
        self._main_layout.addWidget(screen)
        self._main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._main_layout.addWidget(self._jupyter_console_widget)
        screen.continue_button.clicked.connect(self._show_record_videos_screen)

    def _show_record_videos_screen(self):
        clearLayout(self._camera_view_panel_layout)
        self._jupyter_console_widget.print(
            f"Session started with id: {APP_STATE.session_id}"
        )
        screen = RecordVideos()
        self._camera_view_panel_layout.addWidget(screen)

        # self._main_layout.addWidget(self._jupyter_console_widget)

        # self._main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
