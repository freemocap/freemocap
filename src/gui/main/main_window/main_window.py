import os
import shutil
import traceback
from pathlib import Path
from typing import Union

from PyQt6 import QtGui
from PyQt6.QtWidgets import QMainWindow, QSplitter

from src.cameras.detection.models import FoundCamerasResponse
from src.config.home_dir import (
    get_calibration_videos_folder_path,
    get_synchronized_videos_folder_path,
    get_session_folder_path,
    get_session_calibration_toml_file_path,
    get_output_data_folder_path,
    get_most_recent_session_id,
    get_freemocap_data_folder_path,
    get_log_file_path,
)
from src.core_processes.capture_volume_calibration.get_anipose_calibration_object import (
    load_most_recent_anipose_calibration_toml,
    load_calibration_from_session_id,
)
from src.core_processes.mediapipe_2d_skeleton_detector.load_mediapipe2d_data import (
    load_mediapipe2d_data,
)
from src.export_stuff.blender_stuff.export_to_blender import (
    export_to_blender,
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
        self._main_window_width = int(1920 * 0.9)
        self._main_window_height = int(1080 * 0.8)
        APP_STATE.main_window_height = self._main_window_height
        APP_STATE.main_window_width = self._main_window_width

        self.setGeometry(0, 0, self._main_window_width, self._main_window_height)
        self.setMaximumHeight(1000)
        self._main_layout = self._create_main_layout()

        # left side (control) panel
        self._control_panel = self._create_control_panel()
        self._main_layout.addWidget(self._control_panel.frame)

        # middle (viewing) panel
        self._camera_view_panel = self._create_cameras_view_panel()
        self._main_layout.addWidget(self._camera_view_panel.frame)

        # right side (info) panel
        self._right_side_panel = self._create_right_side_panel()

        self._main_layout.addWidget(self._right_side_panel.frame)

        self._thread_worker_manager = ThreadWorkerManager()

        self._connect_signals_to_stuff()
        self._connect_buttons_to_stuff()

        self._auto_process_next_stage = False
        self._cameras_are_popped_out = False
        self._cameras_are_popped_out = False

    def _create_main_layout(self):
        main_layout = QSplitter()
        # widget = QWidget()
        # widget.setLayout(main_layout)
        self.setCentralWidget(main_layout)
        return main_layout

    def _create_control_panel(self):

        panel = ControlPanel()

        width = self._main_window_width * 0.2
        height = self._main_window_height
        panel.frame.setMinimumHeight(height)
        panel.frame.setMinimumWidth(width / 2)
        size_hint = panel.frame.sizeHint()
        size_hint.setWidth(width)
        size_hint.setHeight(height)

        return panel

    def _create_cameras_view_panel(self):
        panel = CameraViewPanel()
        width = self._main_window_width * 0.7
        height = self._main_window_height
        panel.frame.setMinimumHeight(height)
        panel.frame.setMinimumWidth(width / 2)
        size_hint = panel.frame.sizeHint()
        size_hint.setWidth(width)
        size_hint.setHeight(height)

        return panel

    def _create_right_side_panel(self):
        panel = RightSidePanel(
            freemocap_data_folder_path=get_freemocap_data_folder_path()
        )

        width = self._main_window_width * 0.1
        height = self._main_window_height
        panel.frame.setMinimumHeight(height)
        panel.frame.setMinimumWidth(width / 2)
        size_hint = panel.frame.sizeHint()
        size_hint.setWidth(width)
        size_hint.setHeight(height)

        return panel

    def _connect_buttons_to_stuff(self):
        logger.info("Connecting buttons to stuff")

        self._control_panel.create_or_load_new_session_panel.start_new_session_button.clicked.connect(
            lambda: self._start_session(
                self._control_panel._create_or_load_new_session_panel.session_id_input_string
            )
        )

        self._control_panel.create_or_load_new_session_panel.reset_folder_view_to_freemocap_data_folder_button.clicked.connect(
            self._right_side_panel.file_system_view_widget.set_folder_view_to_freemocap_data_folder
        )

        self._control_panel._create_or_load_new_session_panel.load_most_recent_session_button.clicked.connect(
            lambda: self._start_session(get_most_recent_session_id())
        )

        # Camera Control Panel
        self._control_panel.camera_setup_control_panel.apply_settings_to_cameras_button.clicked.connect(
            self._apply_settings_and_launch_camera_threads
        )

        self._control_panel.camera_setup_control_panel.redetect_cameras_button.clicked.connect(
            self._redetect_cameras
        )

        self._control_panel.camera_setup_control_panel.pop_out_cameras_button.clicked.connect(
            self._handle_pop_out_cameras_button_pressed
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
            self._export_to_blender
        )

    def _connect_signals_to_stuff(self):
        logger.info("Connecting signals to stuff")

        self._right_side_panel.file_system_view_widget.load_session_folder_signal.connect(
            self._start_session
        )

        self._thread_worker_manager.camera_detection_finished.connect(
            self._handle_found_cameras_response
        )

        # self._control_panel.camera_setup_control_panel.camera_parameters_updated_signal.connect(
        #     self._apply_settings_and_launch_camera_threads
        # )

        self._camera_view_panel.camera_stream_grid_view.cameras_connected_signal.connect(
            self._camera_view_panel.show_camera_streams
        )

        self._thread_worker_manager.videos_saved_signal.connect(
            self._handle_videos_saved_signal
        )

        self._control_panel.process_session_data_panel.process_all_button.clicked.connect(
            self._fully_process_mocap_videos
        )

        self._thread_worker_manager.start_3d_processing_signal.connect(
            lambda: self._setup_and_launch_triangulate_3d_thread_worker(
                auto_process_next_stage=True
            )
        )

        self._thread_worker_manager.start_blender_processing_signal.connect(
            self._export_to_blender
        )

        self._control_panel.process_session_data_panel.open_in_blender_button.clicked.connect(
            self._open_blender_file
        )

    def _start_session(self, session_id: str):
        self._session_id = session_id

        session_path = get_session_folder_path(self._session_id, create_folder=True)
        self._right_side_panel.file_system_view_widget.set_folder_as_root(session_path)
        self._thread_worker_manager.launch_detect_cameras_worker()

        self._control_panel.toolbox_widget.setCurrentWidget(
            self._control_panel.camera_setup_control_panel
        )

    def _handle_found_cameras_response(
        self, found_cameras_response: FoundCamerasResponse
    ):
        APP_STATE.available_cameras = found_cameras_response.cameras_found_list
        self._control_panel.camera_setup_control_panel.handle_found_cameras_response(
            found_cameras_response
        )

    def _redetect_cameras(self):
        try:
            self._camera_view_panel.camera_stream_grid_view.close_camera_widgets()
        except Exception as e:
            logger.info(e)
            raise e
        self._thread_worker_manager.launch_detect_cameras_worker()

    def _apply_settings_and_launch_camera_threads(
        self, pop_out_camera_windows: bool = False
    ):
        logger.info("Applying settings and launching camera threads")

        self._control_panel.camera_setup_control_panel.apply_settings_to_cameras_button.setText(
            "Apply settings and re-launch cameras"
        )
        self._control_panel.camera_setup_control_panel.pop_out_cameras_button.setEnabled(
            True
        )

        try:
            self._camera_view_panel.camera_stream_grid_view.close_camera_widgets()
        except Exception as e:
            logger.info(e)
            raise e

        dictionary_of_webcam_configs = (
            self._control_panel.camera_setup_control_panel.get_webcam_configs_from_parameter_tree()
        )

        self._cameras_are_popped_out = pop_out_camera_windows

        if self._cameras_are_popped_out:
            self._control_panel.camera_setup_control_panel.pop_out_cameras_button.setText(
                "Re-dock cameras"
            )
        else:
            self._control_panel.camera_setup_control_panel.pop_out_cameras_button.setText(
                "Pop out cameras"
            )

        self._camera_view_panel.camera_stream_grid_view.create_and_start_camera_widgets(
            dictionary_of_webcam_configs=dictionary_of_webcam_configs,
            pop_out_camera_windows=pop_out_camera_windows,
        )

    def _handle_pop_out_cameras_button_pressed(self):
        logger.info("`Pop out cameras` button pressed.")
        if not self._cameras_are_popped_out:
            self._apply_settings_and_launch_camera_threads(pop_out_camera_windows=True)
        else:
            self._apply_settings_and_launch_camera_threads(pop_out_camera_windows=False)

    def _start_recording_videos(self, panel):
        panel.change_button_states_on_record_start()
        self._camera_view_panel.camera_stream_grid_view.start_recording_videos()

    def _stop_recording_videos(self, panel, calibration_videos=False):
        panel.change_button_states_on_record_stop()
        self._camera_view_panel.camera_stream_grid_view.stop_recording_videos()

        dictionary_of_video_recorders = (
            self._camera_view_panel.camera_stream_grid_view.gather_video_recorders()
        )

        if calibration_videos:
            folder_to_save_videos = get_calibration_videos_folder_path(self._session_id)
        else:
            folder_to_save_videos = get_synchronized_videos_folder_path(
                self._session_id
            )

        self._thread_worker_manager.launch_save_videos_thread_worker(
            folder_to_save_videos=folder_to_save_videos,
            dictionary_of_video_recorders=dictionary_of_video_recorders,
            calibration_videos=calibration_videos,
        )

    def _handle_videos_saved_signal(self, calibration_videos: bool = False):
        self._camera_view_panel.camera_stream_grid_view.reset_video_recorders()

        if calibration_videos:
            if (
                self._control_panel._calibrate_capture_volume_panel.process_recording_automatically_checkbox.isChecked()
            ):
                self._setup_and_launch_anipose_calibration_thread_worker()
        else:  # mocap videos
            if (
                self._control_panel.record_synchronized_videos_panel.process_recording_automatically_checkbox.isChecked()
            ):
                self._fully_process_mocap_videos()

    def _setup_and_launch_anipose_calibration_thread_worker(self):
        calibration_videos_folder_path = get_calibration_videos_folder_path(
            self._session_id
        )
        self._thread_worker_manager.launch_anipose_calibration_thread_worker(
            calibration_videos_folder_path=calibration_videos_folder_path,
            charuco_square_size_mm=self._control_panel.calibrate_capture_volume_panel.charuco_square_size,
            session_id=self._session_id,
            jupyter_console_print_function_callable=self._right_side_panel.jupyter_console_widget.print_to_console,
        )

    def _fully_process_mocap_videos(self):
        self._auto_process_next_stage = True
        self._setup_and_launch_mediapipe_2d_detection_thread_worker(
            auto_process_next_stage=True
        )

    def _setup_and_launch_mediapipe_2d_detection_thread_worker(
        self, auto_process_next_stage: bool = False
    ):
        synchronized_videos_folder_path = get_synchronized_videos_folder_path(
            self._session_id
        )
        output_data_folder_path = get_output_data_folder_path(self._session_id)
        self._thread_worker_manager.launch_detect_2d_skeletons_thread_worker(
            synchronized_videos_folder_path=synchronized_videos_folder_path,
            output_data_folder_path=output_data_folder_path,
            auto_process_next_stage=auto_process_next_stage,
        )

    def _setup_and_launch_triangulate_3d_thread_worker(
        self, auto_process_next_stage: bool = False
    ):
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
            mediapipe_confidence_cutoff_threshold=self._control_panel.process_session_data_panel.mediapipe_confidence_cutoff_threshold,
            auto_process_next_stage=auto_process_next_stage,
        )

    def _export_to_blender(self):
        logger.debug(
            "Open Session in Blender button clicked (this will freeze the GUI while it is running, sorry! I tried to run it in a thread instead of a 'subprocess' but I got some kind of permission error when it tried to save the `.blend` file, so.... here we are. Frozen in the GUI.  How are you? "
        )
        # self._thread_worker_manager.launch_export_to_blender_thread_worker(
        #     get_session_folder_path(self._session_id)
        # )
        blender_file_path = export_to_blender(get_session_folder_path(self._session_id))

        if (
            self._control_panel.record_synchronized_videos_panel.open_in_blender_automatically_checkbox.isChecked()
        ):
            self._open_blender_file(blender_file_path)

    def _open_blender_file(self, blender_file_path: Union[str, Path]):
        logger.info(f"Opening {Path(blender_file_path)}")
        os.startfile(str(blender_file_path))

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        logger.info("Close Event detected... ")
        self._camera_view_panel.camera_stream_grid_view.close_camera_widgets()

        try:
            log_file_path = get_log_file_path()
            session_log_path = (
                Path(get_session_folder_path(self._session_id)) / self._session_id
                + "log.log"
            )
            logger.info(
                f"Trying to copy log file from {log_file_path} to session folder: {session_log_path}..."
            )
            shutil.copy2(get_log_file_path(), get_session_folder_path(self._session_id))
        except Exception as e:
            logger.error(f"Something went wrong copying the log file")
            print(e)
