import numpy as np
from PyQt6.QtWidgets import QMainWindow, QHBoxLayout, QWidget

from src.cameras.save_synchronized_videos import save_synchronized_videos
from src.config.home_dir import (
    get_calibration_videos_folder_path,
    get_synchronized_videos_folder_path,
)
from src.gui.main.app_state.app_state import APP_STATE
from src.gui.main.main_window.left_panel_controls.control_panel import ControlPanel
from src.gui.main.main_window.right_side_panel.right_side_panel import (
    RightSidePanel,
)
from src.gui.main.main_window.middle_panel_viewers.camera_view_panel import (
    CameraViewPanel,
)

import logging

from src.gui.main.workers.thread_worker_manager import ThreadWorkerManager

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        logger.info("Creating main window")

        super().__init__()
        self.setWindowTitle("freemocap")
        self._main_window_width = int(1920 * 0.8)
        self._main_window_height = int(1080 * 0.8)
        self.setGeometry(0, 0, self._main_window_width, self._main_window_height)
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

        self._thread_worker_manager = ThreadWorkerManager()

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
        panel.frame.setFixedWidth(self._main_window_width * 0.2)
        panel.frame.setFixedHeight(self._main_window_height)
        return panel

    def _create_cameras_view_panel(self):
        panel = CameraViewPanel()
        panel.frame.setFixedWidth(self._main_window_width * 0.4)
        panel.frame.setFixedHeight(self._main_window_height)
        return panel

    def _create_right_side_panel(self):
        panel = RightSidePanel()
        panel.frame.setFixedWidth(self._main_window_width * 0.4)
        panel.frame.setFixedHeight(self._main_window_height)
        return panel

    def _connect_buttons_to_stuff(self):
        logger.info("Connecting buttons to stuff")
        # after creating new session, set the session folder as root of the file system view widget
        self._control_panel._create_or_load_new_session_panel.submit_button.clicked.connect(
            self._right_side_panel.file_system_view_widget.set_session_path_as_root
        )

        # after creating new session, detect and connect to cameras
        self._control_panel._create_or_load_new_session_panel.submit_button.clicked.connect(
            self._thread_worker_manager.launch_detect_cameras_worker
        )

        # after creating new session, set active toolbox to 'calibrate'
        self._control_panel._create_or_load_new_session_panel.submit_button.clicked.connect(
            lambda: self._control_panel.toolbox_widget.setCurrentWidget(
                self._control_panel.camera_setup_control_panel
            )
        )

        # after clicking "redetect cameras", detect and connect to cameras
        self._control_panel.camera_setup_control_panel.redetect_cameras_button.clicked.connect(
            self._thread_worker_manager.launch_detect_cameras_worker
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
        logger.info("Connecting signals to stuff")

        self._control_panel.camera_setup_control_panel.camera_parameters_updated_signal.connect(
            self._thread_worker_manager.create_camera_widgets_with_running_threads
        )

        self._thread_worker_manager.camera_detection_finished.connect(
            self._control_panel.handle_found_camera_response
        )

        # when 2d data is caluclated, load it into the jupyter console namespace
        self._control_panel.process_session_data_panel.data_2d_done_signal.connect(
            self._load_2d_data_into_jupyter_console
        )
        # when 3d data is calculated, load it into the jupyter console namespace
        self._control_panel.process_session_data_panel.data_3d_done_signal.connect(
            self._load_3d_data_into_jupyter_console
        )

        self._thread_worker_manager.cameras_connected_signal.connect(
            self._camera_view_panel.show_camera_streams
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

        if calibration_videos:
            folder_to_save_videos = get_calibration_videos_folder_path(
                APP_STATE.session_id, create_folder=True
            )
        else:
            folder_to_save_videos = get_synchronized_videos_folder_path(
                APP_STATE.session_id, create_folder=True
            )

        save_synchronized_videos(
            dictionary_of_video_recorders=self._camera_view_panel.camera_stream_grid_view.dictionary_of_video_recorders,
            folder_to_save_videos=folder_to_save_videos,
        )

        if calibration_videos:
            self._camera_view_panel.reconnect_to_cameras()

    def _load_2d_data_into_jupyter_console(self, path_to_data_2d_npy: str):
        self._right_side_panel.jupyter_console_widget.execute(
            f"mediapipe_2d_data = np.load(r'{path_to_data_2d_npy}')"
        )
        self._right_side_panel.jupyter_console_widget.execute("%whos")

    def _load_3d_data_into_jupyter_console(self, path_to_data_3d_npy: str):
        self._right_side_panel.jupyter_console_widget.execute(
            f"mediapipe_3d_data = np.load(r'{path_to_data_3d_npy}')"
        )
        self._right_side_panel.jupyter_console_widget.execute("%whos")
