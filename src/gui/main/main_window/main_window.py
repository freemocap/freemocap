from PyQt6.QtWidgets import QMainWindow, QHBoxLayout, QWidget

from src.gui.main.app_state.app_state import APP_STATE
from src.gui.main.main_window.left_panel_controls.control_panel import ControlPanel
from src.gui.main.main_window.right_side_panel.right_side_panel import (
    RightSidePanel,
)
from src.gui.main.main_window.middle_panel_camera_and_3D_viewer.viewing_panel import (
    ViewingPanel,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("freemocap")
        APP_STATE.main_window_width = int(1920 * 0.8)
        APP_STATE.main_window_height = int(1080 * 0.8)
        self.setGeometry(
            0, 0, APP_STATE.main_window_width, APP_STATE.main_window_height
        )
        self._main_layout = self._create_main_layout()

        # control panel
        self._control_panel = self._create_control_panel()
        self._main_layout.addWidget(self._control_panel.frame)

        # viewing panel
        self._viewing_panel = self._create_viewing_panel()
        self._main_layout.addWidget(self._viewing_panel.frame)

        # jupyter console panel
        self._jupyter_console_widget = self._create_right_side_panel()
        self._main_layout.addWidget(self._jupyter_console_widget.frame)

        self._connect_buttons_to_stuff()

    def _create_main_layout(self):
        main_layout = QHBoxLayout()
        widget = QWidget()
        widget.setLayout(main_layout)
        self.setCentralWidget(widget)
        return main_layout

    def _create_control_panel(self):
        panel = ControlPanel()
        panel.frame.setFixedWidth(APP_STATE.main_window_width * 0.2)
        panel.frame.setFixedHeight(APP_STATE.main_window_height)
        return panel

    def _create_viewing_panel(self):
        panel = ViewingPanel()
        panel.frame.setFixedWidth(APP_STATE.main_window_width * 0.5)
        panel.frame.setFixedHeight(APP_STATE.main_window_height)
        return panel

    def _create_right_side_panel(self):
        panel = RightSidePanel()
        panel.frame.setFixedWidth(APP_STATE.main_window_width * 0.3)
        panel.frame.setFixedHeight(APP_STATE.main_window_height)
        return panel

    def _connect_buttons_to_stuff(self):
        # when 'start new session' button is clicked, connect to cameras and display in `viewing panel`
        self._control_panel.select_workflow_screen.start_new_session_button.clicked.connect(
            self._viewing_panel.detect_and_connect_to_cameras
        )

        # I don't know how to make this happen automatically via 'emitted signals' but I DO know how to connect it to a dumb button, lol
        self._viewing_panel.update_camera_configs_button.clicked.connect(
            self._control_panel.update_camera_configs
        )

        self._control_panel.camera_setup_control_panel.apply_settings_to_cameras_button.clicked.connect(
            self._apply_webcam_configs_and_reconnect
        )

    def _apply_webcam_configs_and_reconnect(self):
        self._control_panel.camera_setup_control_panel.save_settings_to_app_state()
        self._viewing_panel.reconnect_to_cameras()
