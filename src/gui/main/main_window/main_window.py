from PyQt6.QtWidgets import QMainWindow, QHBoxLayout, QWidget

from src.config.home_dir import (
    get_calibration_videos_folder_path,
    get_synchronized_videos_folder_path,
    get_session_folder_path,
    get_session_calibration_toml_file_path,
    get_output_data_folder_path,
)
from src.core_processes.capture_volume_calibration.get_anipose_calibration_object import (
    load_most_recent_anipose_calibration_toml,
    load_calibration_from_session_id,
)
from src.core_processes.mediapipe_2d_skeleton_detector.load_mediapipe2d_data import (
    load_mediapipe2d_data,
)
from src.export_stuff.blender_stuff.open_session_in_blender import (
    open_session_in_blender,
)
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

        self._control_panel._create_or_load_new_session_panel.start_new_session_button.clicked.connect(
            self._start_new_session
        )

        # Camera Control Panel
        self._control_panel.camera_setup_control_panel.apply_settings_to_cameras_button.clicked.connect(
            self._control_panel.camera_setup_control_panel.get_webcam_configs_from_parameter_tree
        )

        self._control_panel.camera_setup_control_panel.redetect_cameras_button.clicked.connect(
            self._thread_worker_manager.launch_detect_cameras_worker
        )

        # Calibration panel
        self._control_panel.calibrate_capture_volume_panel.start_recording_button.clicked.connect(
            lambda: self._start_recording_videos(
                panel=self._control_panel.calibrate_capture_volume_panel
            )
        )

        self._control_panel.calibrate_capture_volume_panel.stop_recording_button.clicked.connect(
            lambda: self._stop_recording_videos(
                panel=self._control_panel.calibrate_capture_volume_panel,
                calibration_videos=True,
            )
        )

        self._control_panel.calibrate_capture_volume_panel.calibrate_capture_volume_from_videos_button.clicked.connect(
            self._setup_and_launch_anipose_calibration_thread_worker
        )

        # RecordVideos panel
        self._control_panel.record_synchronized_videos_panel.start_recording_button.clicked.connect(
            lambda: self._start_recording_videos(
                panel=self._control_panel.record_synchronized_videos_panel,
            )
        )

        self._control_panel.record_synchronized_videos_panel.stop_recording_button.clicked.connect(
            lambda: self._stop_recording_videos(
                panel=self._control_panel.record_synchronized_videos_panel
            )
        )

        # ProcessVideos panel
        self._control_panel.process_session_data_panel.detect_2d_skeletons_button.clicked.connect(
            self._setup_and_launch_mediapipe_2d_detection_thread_worker
        )

        self._control_panel.process_session_data_panel.triangulate_3d_data_button.clicked.connect(
            self._setup_and_launch_triangulate_3d_thread_worker
        )

        self._control_panel.process_session_data_panel.open_in_blender_button.clicked.connect(
            self._launch_blender_export_subprocess
        )

    def _connect_signals_to_stuff(self):
        logger.info("Connecting signals to stuff")

        self._thread_worker_manager.camera_detection_finished.connect(
            self._control_panel.handle_found_camera_response
        )

        self._control_panel.camera_setup_control_panel.camera_parameters_updated_signal.connect(
            self._thread_worker_manager.create_camera_widgets_with_running_threads
        )

        self._thread_worker_manager.cameras_connected_signal.connect(
            self._camera_view_panel.show_camera_streams
        )

    def _start_new_session(self):
        self._session_id = (
            self._control_panel._create_or_load_new_session_panel.session_id_input_string
        )

        session_path = get_session_folder_path(self._session_id, create_folder=True)
        self._right_side_panel.file_system_view_widget.set_session_path_as_root(
            session_path
        )
        self._thread_worker_manager.launch_detect_cameras_worker()
        self._control_panel.toolbox_widget.setCurrentWidget(
            self._control_panel.camera_setup_control_panel
        )

    def _start_recording_videos(self, panel):
        panel.change_button_states_on_record_start()
        self._thread_worker_manager.start_recording_videos()

    def _stop_recording_videos(self, panel, calibration_videos=False):
        panel.change_button_states_on_record_stop()
        self._thread_worker_manager.stop_recording_videos()

        if calibration_videos:
            path_to_save_videos = get_calibration_videos_folder_path(self._session_id)
        else:
            path_to_save_videos = get_synchronized_videos_folder_path(self._session_id)

        self._thread_worker_manager.launch_save_videos_thread_worker(
            path_to_save_videos
        )

    def _setup_and_launch_anipose_calibration_thread_worker(self):
        calibration_videos_folder_path = get_calibration_videos_folder_path(
            self._session_id
        )
        self._thread_worker_manager.launch_anipose_calibration_thread_worker(
            calibration_videos_folder_path=calibration_videos_folder_path,
            charuco_square_size_mm=float(
                self._control_panel.calibrate_capture_volume_panel.charuco_square_size
            ),
        )

    def _setup_and_launch_mediapipe_2d_detection_thread_worker(self):
        synchronized_videos_folder_path = get_synchronized_videos_folder_path(
            self._session_id
        )
        output_data_folder_path = get_output_data_folder_path(self._session_id)
        self._thread_worker_manager.launch_detect_2d_skeletons_thread_worker(
            synchronized_videos_folder_path=synchronized_videos_folder_path,
            output_data_folder_path=output_data_folder_path,
        )

    def _setup_and_launch_triangulate_3d_thread_worker(self):
        if (
            self._control_panel.calibrate_capture_volume_panel.use_previous_calibration_box_is_checked
        ):
            anipose_calibration_object = load_most_recent_anipose_calibration_toml(
                get_session_folder_path(self._session_id)
            )
        else:
            anipose_calibration_object = load_calibration_from_session_id(
                get_session_calibration_toml_file_path(self._session_id)
            )

        output_data_folder_path = get_output_data_folder_path(self._session_id)
        mediapipe_2d_data = load_mediapipe2d_data(output_data_folder_path)

        self._thread_worker_manager.launch_triangulate_3d_data_thread_worker(
            anipose_calibration_object=anipose_calibration_object,
            mediapipe_2d_data=mediapipe_2d_data,
            output_data_folder_path=output_data_folder_path,
        )

    def _launch_blender_export_subprocess(self):
        print(f"Open in Blender : {self._session_id}")
        open_session_in_blender(self._session_id)
