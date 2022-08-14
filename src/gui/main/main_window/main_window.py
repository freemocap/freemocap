from PyQt6.QtWidgets import QMainWindow, QHBoxLayout, QWidget

from src.cameras.save_synchronized_videos import save_synchronized_videos
from src.gui.main.app_state.app_state import APP_STATE
from src.gui.main.main_window.left_panel_controls.control_panel import ControlPanel
from src.gui.main.main_window.right_side_panel.right_side_panel import (
    RightSidePanel,
)
from src.gui.main.main_window.middle_panel_camera_and_3D_viewer.camera_view_panel import (
    CameraViewPanel,
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
        self._camera_view_panel = self._create_cameras_view_panel()
        self._main_layout.addWidget(self._camera_view_panel.frame)

        # jupyter console panel
        self._right_side_panel = self._create_right_side_panel()
        self._main_layout.addWidget(self._right_side_panel.frame)

        self._connect_signals_to_stuff()
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

    def _create_cameras_view_panel(self):
        panel = CameraViewPanel()
        panel.frame.setFixedWidth(APP_STATE.main_window_width * 0.5)
        panel.frame.setFixedHeight(APP_STATE.main_window_height)
        return panel

    def _create_right_side_panel(self):
        panel = RightSidePanel()
        panel.frame.setFixedWidth(APP_STATE.main_window_width * 0.3)
        panel.frame.setFixedHeight(APP_STATE.main_window_height)
        return panel

    def _connect_buttons_to_stuff(self):
        # after creating new session, set the session folder as root of the file system view widget
        self._control_panel._create_new_session_panel.submit_button.clicked.connect(
            self._right_side_panel.file_system_view_widget.set_session_path_as_root
        )

        # after creating new session, detect and connect to cameras
        self._control_panel._create_new_session_panel.submit_button.clicked.connect(
            self._camera_view_panel.detect_and_connect_to_cameras
        )

        # after creating new session, set active toolbox to 'calibrate'
        self._control_panel._create_new_session_panel.submit_button.clicked.connect(
            lambda: self._control_panel.toolbox_widget.setCurrentWidget(
                self._control_panel.camera_setup_control_panel
            )
        )

        # after clicking "apply new settings to cameras" button, reconnect to cameras with new User specified `webcam_configs`
        self._control_panel.camera_setup_control_panel.apply_settings_to_cameras_button.clicked.connect(
            self._apply_webcam_configs_and_reconnect
        )

        # Calibration panel - when click 'Begin Recording' button, start recording
        self._control_panel.calibrate_capture_volume_panel.start_recording_button.clicked.connect(
            lambda: self._start_recording_videos(
                panel=self._control_panel.calibrate_capture_volume_panel
            )
        )

        # Calibration panel -  when click 'Stop Recording' button, stop recording (and save the videos as 'calibration' b/c they came from the calibrate panel')
        self._control_panel.calibrate_capture_volume_panel.stop_recording_button.clicked.connect(
            lambda: self._stop_recording_videos(calibration_videos=True)
        )

        # RecordVideos panel - when click 'Begin Recording' button, start recording
        self._control_panel.record_synchronized_videos_panel.start_recording_button.clicked.connect(
            lambda: self._start_recording_videos(
                panel=self._control_panel.record_synchronized_videos_panel
            )
        )

        # RecordVideos panel -  when click 'Stop Recording' button, stop recording (and save the videos as 'calibration' b/c they came from the calibrate panel')
        self._control_panel.record_synchronized_videos_panel.stop_recording_button.clicked.connect(
            lambda: self._stop_recording_videos(calibration_videos=False)
        )

    def _connect_signals_to_stuff(self):
        # update the 'camera configs' panel when the 'camera view panel' connects to cameras
        self._camera_view_panel.camera_stream_grid_view.cameras_connected_signal.connect(
            self._control_panel.update_camera_configs
        )

    def _apply_webcam_configs_and_reconnect(self):
        self._control_panel.camera_setup_control_panel.save_settings_to_app_state()
        self._camera_view_panel.reconnect_to_cameras()

    def _start_recording_videos(self, panel):
        panel.change_button_states_on_record_start()
        self._camera_view_panel.camera_stream_grid_view.start_recording_videos()

    def _stop_recording_videos(self, calibration_videos: bool = False):
        self._control_panel.calibrate_capture_volume_panel.change_button_states_on_record_stop()
        self._camera_view_panel.camera_stream_grid_view.stop_recording_videos()
        save_synchronized_videos(
            self._camera_view_panel.camera_stream_grid_view.video_recorders,
            calibration_videos=calibration_videos,
        )

        if calibration_videos:
            self._camera_view_panel.reconnect_to_cameras()
