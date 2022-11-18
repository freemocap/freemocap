import os
import shutil
from pathlib import Path
from typing import Union

import pandas as pd
from PyQt6 import QtGui
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMainWindow, QSplitter, QFileDialog, QMenuBar, QMenu

from src.blender_stuff.export_to_blender import export_to_blender
from src.cameras.detection.models import FoundCamerasResponse
from src.config.home_dir import (
    get_calibration_videos_folder_path,
    get_synchronized_videos_folder_path,
    get_session_folder_path,
    get_session_calibration_toml_file_path,
    get_output_data_folder_path,
    get_most_recent_session_id,
    get_freemocap_data_folder_path,
    get_annotated_videos_folder_path,
    get_skeleton_body_csv_path,
    get_blender_file_path,
    get_raw_data_folder_path,
    PARTIALLY_PROCESSED_DATA_FOLDER_NAME,
    MEDIAPIPE_3D_ORIGIN_ALIGNED_NPY_FILE_NAME,
)
from src.core_processes.capture_volume_calibration.charuco_board_detection.dataclasses.charuco_board_definition import (
    CharucoBoardDefinition,
)
from src.core_processes.capture_volume_calibration.get_anipose_calibration_object import (
    load_most_recent_anipose_calibration_toml,
    load_calibration_from_session_id,
    load_anipose_calibration_toml_from_path,
)
from src.core_processes.mediapipe_stuff.load_mediapipe2d_data import (
    load_mediapipe2d_data,
)
from src.core_processes.mediapipe_stuff.load_mediapipe3d_data import (
    load_raw_mediapipe3d_data,
    load_post_processed_mediapipe3d_data,
    load_skeleton_reprojection_error_data,
)
from src.core_processes.post_process_skeleton_data.estimate_skeleton_segment_lengths import (
    mediapipe_skeleton_segment_definitions,
    estimate_skeleton_segment_lengths,
    save_skeleton_segment_lengths_to_json,
)

from src.gui.main.app import get_qt_app
from src.gui.main.app_state.app_state import APP_STATE
from src.gui.main.main_window.left_panel_controls.control_panel import ControlPanel
from src.gui.main.main_window.right_side_panel.right_side_panel import (
    RightSidePanel,
)
from src.gui.main.main_window.middle_panel_viewers.session_playback_view.middle_viewing_panel import (
    MiddleViewingPanel,
)

import logging

from src.gui.main.workers.thread_worker_manager import ThreadWorkerManager
from src.log.config import LOG_FILE_PATH

from src.sending_anonymous_user_info_to_places.send_pipedream_ping import (
    send_pipedream_ping,
)

# reboot GUI method based on this - https://stackoverflow.com/a/56563926/14662833
EXIT_CODE_REBOOT = -123456789

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        self._pipedream_ping_dictionary = {"gui_window": "launched"}
        logger.info("Creating main window")

        super().__init__()

        self.setWindowTitle("freemocap \U0001F480 \U00002728")
        # self._set_icon()

        self._main_window_width = int(1920 * 0.9)
        self._main_window_height = int(1080 * 0.8)
        APP_STATE.main_window_height = self._main_window_height
        APP_STATE.main_window_width = self._main_window_width

        self.setGeometry(0, 0, self._main_window_width, self._main_window_height)
        self._main_layout = self._create_main_layout()
        self._main_layout.setMaximumHeight(self._main_window_height)
        # left side (control) panel
        self._control_panel = self._create_control_panel()
        self._main_layout.addWidget(self._control_panel.frame)

        # middle (viewing) panel
        self._middle_viewing_panel = self._create_middle_viewing_panel()
        self._main_layout.addWidget(self._middle_viewing_panel.frame)

        # right side (info) panel
        self._right_side_panel = self._create_right_side_panel()

        self._main_layout.addWidget(self._right_side_panel.frame)

        self._thread_worker_manager = ThreadWorkerManager(
            session_progress_dictionary=self._pipedream_ping_dictionary
        )

        # actions, signals and slots, o my
        self._create_actions()
        self._create_menu_bar()
        self._connect_actions_to_slots()
        self._connect_signals_to_stuff()
        self._connect_buttons_to_stuff()

        self._auto_launch_camera_streams = False
        self._auto_process_next_stage = False
        self._cameras_are_popped_out = False
        self._cameras_are_popped_out = False

        self._session_id = None

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
        panel.frame.setMinimumHeight(height / 2)
        panel.frame.setMinimumWidth(width / 2)
        size_hint = panel.frame.sizeHint()
        size_hint.setWidth(width)
        size_hint.setHeight(height)

        return panel

    def _create_middle_viewing_panel(self):
        panel = MiddleViewingPanel()
        width = self._main_window_width * 0.7
        height = self._main_window_height
        panel.frame.setMinimumHeight(height / 2)
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
        # panel.frame.setMinimumHeight(height)
        panel.frame.setMinimumWidth(width / 2)
        size_hint = panel.frame.sizeHint()
        size_hint.setWidth(width)
        size_hint.setHeight(height)

        return panel

    def _create_actions(self):
        # File
        self._new_session_action = QAction("&Start New Session", parent=self)
        self._new_session_action.setShortcut("Ctrl+N")

        self._load_most_recent_session_action = QAction(
            "Load &Most Recent Session", parent=self
        )
        self._load_most_recent_session_action.setShortcut("Ctrl+D")

        self._load_session_action = QAction("&Load Session...", parent=self)
        self._load_session_action.setShortcut("Ctrl+O")

        self._import_videos_action = QAction(
            "Import Synchronized &Videos...", parent=self
        )
        self._import_videos_action.setShortcut("Ctrl+I")

        self._reboot_gui_action = QAction("&Reboot GUI", parent=self)
        self._reboot_gui_action.setShortcut("Ctrl+R")

        self._exit_action = QAction("E&xit", parent=self)
        self._exit_action.setShortcut("Ctrl+Q")

        # Help
        self._open_docs_action = QAction("Open  &Documentation", parent=self)
        self._about_us_action = QAction("&About Us", parent=self)

        # Navigation
        self._show_camera_control_panel_action = QAction(
            "&1 - Show Camera Control Panel", parent=self
        )
        self._show_camera_control_panel_action.setShortcut("Ctrl+1")

        self._show_calibrate_capture_volume_panel_action = QAction(
            "&2 - Show Calibrate Capture Volume Panel", parent=self
        )
        self._show_calibrate_capture_volume_panel_action.setShortcut("Ctrl+2")

        self._show_motion_capture_videos_panel_action = QAction(
            "&3 - Show Motion Capture Videos Panel", parent=self
        )
        self._show_motion_capture_videos_panel_action.setShortcut("Ctrl+3")

        # Support
        self._donate_action = QAction("&Donate", parent=self)
        self._send_usage_statistics_action = QAction(
            "Send &User Statistics", parent=self
        )
        self._user_survey_action = QAction("&User Survey", parent=self)

    def _create_menu_bar(self):
        """
        based mostly on: https://realpython.com/python-menus-toolbars/
        """
        menu_bar = QMenuBar()
        self.setMenuBar(menu_bar)

        # file menu
        file_menu = QMenu("&File", parent=menu_bar)
        menu_bar.addMenu(file_menu)

        file_menu.addAction(self._new_session_action)
        file_menu.addAction(self._load_most_recent_session_action)
        file_menu.addAction(self._load_session_action)
        file_menu.addAction(self._import_videos_action)
        file_menu.addAction(self._reboot_gui_action)
        file_menu.addAction(self._exit_action)

        # navigation menu
        navigation_menu = QMenu("Na&vigation", parent=menu_bar)
        menu_bar.addMenu(navigation_menu)
        navigation_menu.addAction(self._show_camera_control_panel_action)
        navigation_menu.addAction(self._show_calibrate_capture_volume_panel_action)
        navigation_menu.addAction(self._show_motion_capture_videos_panel_action)

        # help menu
        help_menu = QMenu("&Help", parent=menu_bar)
        menu_bar.addMenu(help_menu)
        help_menu.setEnabled(False)

        help_menu.addAction(self._open_docs_action)
        help_menu.addAction(self._about_us_action)

        # support menu
        support_menu = QMenu(
            "\U00002665 &Support the FreeMoCap Project", parent=menu_bar
        )
        support_menu.setEnabled(False)
        menu_bar.addMenu(support_menu)

        support_menu.addAction(self._donate_action)
        support_menu.addAction(self._send_usage_statistics_action)
        support_menu.addAction(self._user_survey_action)

        return menu_bar

    def _connect_actions_to_slots(self):

        self._new_session_action.triggered.connect(
            self._middle_viewing_panel.welcome_create_or_load_session_panel.show_new_session_setup_view
        )

        self._load_most_recent_session_action.triggered.connect(
            lambda: self._start_session(get_most_recent_session_id())
        )

        self._load_session_action.triggered.connect(self._load_session_dialog)

        self._import_videos_action.triggered.connect(
            self._middle_viewing_panel.welcome_create_or_load_session_panel.show_import_videos_view
        )

        self._reboot_gui_action.triggered.connect(self._reboot_gui)

        self._exit_action.triggered.connect(self.close)

        # Navigation Menu

        self._show_camera_control_panel_action.triggered.connect(
            lambda: self._control_panel.toolbox_widget.setCurrentWidget(
                self._control_panel.camera_setup_control_panel
            )
        )
        self._show_calibrate_capture_volume_panel_action.triggered.connect(
            lambda: self._control_panel.toolbox_widget.setCurrentWidget(
                self._control_panel.calibrate_capture_volume_panel
            )
        )
        self._show_motion_capture_videos_panel_action.triggered.connect(
            lambda: self._control_panel.toolbox_widget.setCurrentWidget(
                self._control_panel.motion_capture_panel
            )
        )

        # self._open_docs_action.triggered.connect()
        # self._about_us_action.triggered.connect()
        # self._donate_action.triggered.connect()
        # self._send_usage_statistics_action.triggered.connect()
        # self._user_survey_action.triggered.connect()

    def _connect_buttons_to_stuff(self):
        logger.info("Connecting buttons to stuff")

        # Welcome Panel
        self._middle_viewing_panel.welcome_create_or_load_session_panel.start_session_button.clicked.connect(
            lambda: self._start_session(
                session_id=self._middle_viewing_panel.welcome_create_or_load_session_panel.session_id_input_string,
                new_session=True,
            )
        )

        self._middle_viewing_panel.welcome_create_or_load_session_panel.load_most_recent_session_button.clicked.connect(
            self._load_most_recent_session_action.trigger
        )

        self._middle_viewing_panel.welcome_create_or_load_session_panel.load_session_button.clicked.connect(
            self._load_session_action.trigger
        )

        self._middle_viewing_panel.welcome_create_or_load_session_panel.synchronized_videos_selection_dialog_button.clicked.connect(
            self._import_videos
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

        self._control_panel.camera_setup_control_panel.close_cameras_button.clicked.connect(
            self._middle_viewing_panel.camera_stream_grid_view.close_camera_widgets
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
        self._control_panel.motion_capture_panel.start_recording_button.clicked.connect(
            lambda: self._start_recording_videos(
                panel=self._control_panel.motion_capture_panel,
            )
        )

        self._control_panel.motion_capture_panel.stop_recording_button.clicked.connect(
            lambda: self._stop_recording_videos(
                panel=self._control_panel.motion_capture_panel
            )
        )

        # (record videos) ProcessVideos panel
        self._control_panel.process_session_data_panel.process_all_button.clicked.connect(
            self._fully_process_mocap_videos
        )

        self._control_panel.process_session_data_panel.detect_2d_skeletons_button.clicked.connect(
            self._setup_and_launch_mediapipe_2d_detection_thread_worker
        )

        self._control_panel.process_session_data_panel.triangulate_3d_data_button.clicked.connect(
            self._setup_and_launch_triangulate_3d_thread_worker
        )

        self._control_panel.process_session_data_panel.gap_fill_filter_origin_align_button.clicked.connect(
            self._setup_and_launch_gap_fill_filter_origin_align_thread_worker
        )

        self._control_panel.process_session_data_panel.convert_npy_to_csv_button.clicked.connect(
            self._setup_and_launch_convert_npy_to_csv_thread_worker
        )

        # Visualize Mocap Data panel
        self._control_panel.visualize_session_data_panel.load_session_data_button.clicked.connect(
            self._visualize_motion_capture_data
        )
        self._control_panel.visualize_session_data_panel.generate_blend_file_button.clicked.connect(
            self._generate_blend_file
        )

        self._control_panel.visualize_session_data_panel.generate_blend_file_button.clicked.connect(
            self._open_blender_file
        )
        # (right side) File viewer panel
        self._right_side_panel.file_system_view_widget.show_current_session_folder_button.clicked.connect(
            lambda: self._set_session_folder_as_root_for_file_viewer(self._session_id)
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

        self._middle_viewing_panel.camera_stream_grid_view.cameras_connected_signal.connect(
            self._middle_viewing_panel.show_camera_streams
        )

        self._thread_worker_manager.videos_saved_signal.connect(
            self._handle_videos_saved_signal
        )

        self._thread_worker_manager.start_3d_processing_signal.connect(
            lambda: self._setup_and_launch_triangulate_3d_thread_worker(
                auto_process_next_stage=True
            )
        )

        self._thread_worker_manager.start_post_processing_signal.connect(
            lambda: self._setup_and_launch_gap_fill_filter_origin_align_thread_worker(
                auto_process_next_stage=True
            )
        )

        self._thread_worker_manager.start_convert_npy_to_to_csv_signal.connect(
            lambda: self._setup_and_launch_convert_npy_to_csv_thread_worker(
                auto_process_next_stage=True
            )
        )

        self._thread_worker_manager.start_blender_processing_signal.connect(
            self._generate_blend_file
        )

        self._thread_worker_manager.start_session_data_visualization_signal.connect(
            self._visualize_motion_capture_data
        )

    def _set_session_folder_as_root_for_file_viewer(self, session_id: str):
        session_path = get_session_folder_path(session_id, create_folder=True)
        self._right_side_panel.file_system_view_widget.set_folder_as_root(session_path)

    def _load_session_dialog(self):
        # from this tutorial - https://www.youtube.com/watch?v=gg5TepTc2Jg&t=649s
        user_selected_path = QFileDialog.getExistingDirectory(
            self,
            "Select the session folder you want to load...",
            get_freemocap_data_folder_path(),
        )

        self._session_id = str(
            Path(user_selected_path).relative_to(get_freemocap_data_folder_path())
        )

        logger.info(
            f"User selected session path:{user_selected_path}, `session_id` set to  {self._session_id}"
        )

        self._start_session(self._session_id)

    def _import_videos(self):
        # from this tutorial - https://www.youtube.com/watch?v=gg5TepTc2Jg&t=649s
        external_videos_path = QFileDialog.getExistingDirectory(
            self,
            "Select a folder containig synchronized videos (each video must have *exactly* the same number of frames)",
            str(Path.home()),
        )
        self._session_id = (
            self._middle_viewing_panel.welcome_create_or_load_session_panel.session_id_input_string
        )

        synchronized_videos_folder_path = get_synchronized_videos_folder_path(
            self._session_id, create_folder=True
        )

        logger.info(
            f"Copying videos from {external_videos_path} to {synchronized_videos_folder_path}"
        )

        for video_path in Path(external_videos_path).glob("*.mp4"):
            shutil.copy(video_path, synchronized_videos_folder_path)

        self._start_session(self._session_id)

    def _start_session(self, session_id: str, new_session: bool = False):

        self._session_id = session_id
        self._control_panel.enable_toolbox_panels()
        self._set_session_folder_as_root_for_file_viewer(self._session_id)
        self._right_side_panel.file_system_view_widget.show_current_session_folder_button.setEnabled(
            True
        )

        text = (
            self._right_side_panel.file_system_view_widget.show_current_session_folder_button.text()
        )
        self._right_side_panel.file_system_view_widget.show_current_session_folder_button.setText(
            text + ", session_id: " + self._session_id
        )

        if (
            new_session
            and self._middle_viewing_panel.welcome_create_or_load_session_panel.auto_detect_cameras_checkbox.isChecked()
        ):
            self._thread_worker_manager.launch_detect_cameras_worker()

        self._show_camera_control_panel_action.trigger()

        self._middle_viewing_panel.show_camera_streams()

        if (
            new_session
            and self._middle_viewing_panel.welcome_create_or_load_session_panel.auto_connect_to_cameras_checkbox.isChecked()
        ):
            self._auto_launch_camera_streams = True

    def _handle_found_cameras_response(
        self, found_cameras_response: FoundCamerasResponse
    ):
        APP_STATE.available_cameras = found_cameras_response.cameras_found_list
        self._control_panel.camera_setup_control_panel.handle_found_cameras_response(
            found_cameras_response
        )

        if self._auto_launch_camera_streams:
            self._auto_launch_camera_streams = False
            self._apply_settings_and_launch_camera_threads()

    def _redetect_cameras(self):
        try:
            self._middle_viewing_panel.camera_stream_grid_view.close_camera_widgets()
        except Exception as e:
            logger.info(e)
            raise e
        self._thread_worker_manager.launch_detect_cameras_worker()

    def _apply_settings_and_launch_camera_threads(
        self, pop_out_camera_windows: bool = False
    ):
        logger.info("Applying settings and launching camera threads")

        self._control_panel.camera_setup_control_panel.pop_out_cameras_button.setEnabled(
            True
        )

        try:
            self._middle_viewing_panel.camera_stream_grid_view.close_camera_widgets()
        except Exception as e:
            logger.info(e)
            raise e

        dictionary_of_webcam_configs = (
            self._control_panel.camera_setup_control_panel.get_webcam_configs_from_parameter_tree()
        )

        self._cameras_are_popped_out = pop_out_camera_windows

        self._control_panel.camera_setup_control_panel.pop_out_cameras_button.setEnabled(
            not pop_out_camera_windows
        )
        self._control_panel.camera_setup_control_panel.dock_cameras_button.setEnabled(
            pop_out_camera_windows
        )

        self._middle_viewing_panel.camera_stream_grid_view.create_and_start_camera_widgets(
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
        self._middle_viewing_panel.camera_stream_grid_view.start_recording_videos()

    def _stop_recording_videos(self, panel, calibration_videos=False):
        panel.change_button_states_on_record_stop()
        self._middle_viewing_panel.camera_stream_grid_view.stop_recording_videos()

        dictionary_of_video_recorders = (
            self._middle_viewing_panel.camera_stream_grid_view.gather_video_recorders()
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
        self._middle_viewing_panel.camera_stream_grid_view.reset_video_recorders()

        if calibration_videos:
            if (
                self._control_panel.calibrate_capture_volume_panel.process_recording_automatically_checkbox.isChecked()
            ):
                self._setup_and_launch_anipose_calibration_thread_worker()
        else:  # mocap videos
            if (
                self._control_panel.motion_capture_panel.process_recording_automatically_checkbox.isChecked()
            ):
                self._fully_process_mocap_videos()

    def _setup_and_launch_anipose_calibration_thread_worker(self):
        calibration_videos_folder_path = get_calibration_videos_folder_path(
            self._session_id
        )
        if (
            not Path(calibration_videos_folder_path).exists()
            or len(list(Path(calibration_videos_folder_path).glob("*.mp4"))) == 0
        ):
            logger.info(
                f"Calibration videos folder does not exist (or its empty): {calibration_videos_folder_path}, copying vidoes from `synchronized_videos` to `calibration_videos` and trying with that"
            )
            Path(calibration_videos_folder_path).mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                get_synchronized_videos_folder_path(self._session_id),
                calibration_videos_folder_path,
                dirs_exist_ok=True,
            )

        charuco_board_definition = self._get_user_specified_charuco_definition()
        logger.info(
            f"Launching Anipose calibration thread worker with the following parameters: {charuco_board_definition.__dict__}"
        )
        self._thread_worker_manager.launch_anipose_calibration_thread_worker(
            charuco_board_definition=charuco_board_definition,
            calibration_videos_folder_path=calibration_videos_folder_path,
            charuco_square_size_mm=self._control_panel.calibrate_capture_volume_panel.charuco_square_size,
            session_id=self._session_id,
            jupyter_console_print_function_callable=self._right_side_panel.jupyter_console_widget.print_to_console,
        )

    def _get_user_specified_charuco_definition(self):
        charuco_board_definition = CharucoBoardDefinition()
        user_charuco_selection = (
            self._control_panel.calibrate_capture_volume_panel.charuco_combo_box_selection
        )

        if user_charuco_selection == "Default (3x5 squares)":
            charuco_board_definition.number_of_squares_width = 5
            charuco_board_definition.number_of_squares_height = 3
        elif user_charuco_selection == "Pre-Alpha (5x7 squares)":
            charuco_board_definition.number_of_squares_width = 7
            charuco_board_definition.number_of_squares_height = 5

        return charuco_board_definition

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
        raw_data_folder_path = get_raw_data_folder_path(self._session_id)
        self._thread_worker_manager.launch_detect_2d_skeletons_thread_worker(
            synchronized_videos_folder_path=synchronized_videos_folder_path,
            output_data_folder_path=raw_data_folder_path,
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

            calibration_toml_filename = f"camera_calibration_data.toml"
            camera_calibration_toml_path = (
                Path(get_session_folder_path(self._session_id))
                / calibration_toml_filename
            )
            anipose_calibration_object.dump(camera_calibration_toml_path)

        elif (
            self._control_panel.calibrate_capture_volume_panel.load_camera_calibration_checkbox_is_checked
        ):
            anipose_calibration_object = load_anipose_calibration_toml_from_path(
                self._control_panel.calibrate_capture_volume_panel.user_selected_calibration_toml_path,
                get_session_folder_path(self._session_id),
            )
            if anipose_calibration_object is None:
                logger.error(
                    "Could not load user selected calibration file! Aborting '_setup_and_launch_triangulate_3d_thread_worker'..."
                )
                return

        else:
            anipose_calibration_object = load_calibration_from_session_id(
                get_session_calibration_toml_file_path(self._session_id)
            )

        raw_data_folder_path = get_raw_data_folder_path(self._session_id)
        mediapipe_2d_data = load_mediapipe2d_data(raw_data_folder_path)

        self._thread_worker_manager.launch_triangulate_3d_data_thread_worker(
            anipose_calibration_object=anipose_calibration_object,
            mediapipe_2d_data=mediapipe_2d_data,
            output_data_folder_path=raw_data_folder_path,
            mediapipe_confidence_cutoff_threshold=self._control_panel.process_session_data_panel.mediapipe_confidence_cutoff_threshold,
            auto_process_next_stage=auto_process_next_stage,
            use_triangulate_ransac=self._control_panel.process_session_data_panel.use_triangulate_ransac_checkbox.isChecked(),
        )

    def _setup_and_launch_gap_fill_filter_origin_align_thread_worker(
        self, auto_process_next_stage: bool = False
    ):
        output_data_folder_path = Path(get_output_data_folder_path(self._session_id))

        skel3d_frame_marker_xyz = load_raw_mediapipe3d_data(output_data_folder_path)
        skeleton_reprojection_error_fr_mar = load_skeleton_reprojection_error_data(
            output_data_folder_path
        )

        data_save_path = output_data_folder_path / PARTIALLY_PROCESSED_DATA_FOLDER_NAME
        data_save_path.mkdir(exist_ok=True)
        sampling_rate = 30
        cut_off = 7
        order = 4
        reference_frame_number = None

        self._thread_worker_manager.launch_post_process_3d_data_thread_worker(
            skel3d_frame_marker_xyz=skel3d_frame_marker_xyz,
            skeleton_reprojection_error_fr_mar=skeleton_reprojection_error_fr_mar,
            data_save_path=data_save_path,
            sampling_rate=sampling_rate,
            cut_off=cut_off,
            order=order,
            reference_frame_number=reference_frame_number,
            auto_process_next_stage=auto_process_next_stage,
        )

    def _setup_and_launch_convert_npy_to_csv_thread_worker(
        self, auto_process_next_stage: bool = False
    ):
        logger.info("Launching convert npy to csv thread worker")

        output_data_folder_path = Path(get_output_data_folder_path(self._session_id))
        mediapipe3d_xyz_file_path = (
            Path(output_data_folder_path)
            / PARTIALLY_PROCESSED_DATA_FOLDER_NAME
            / MEDIAPIPE_3D_ORIGIN_ALIGNED_NPY_FILE_NAME
        )
        skel3d_frame_marker_xyz = load_post_processed_mediapipe3d_data(
            mediapipe3d_xyz_file_path
        )

        self._thread_worker_manager.launch_convert_npy_to_csv_thread_worker(
            skel3d_frame_marker_xyz=skel3d_frame_marker_xyz,
            output_data_folder_path=output_data_folder_path,
            auto_process_next_stage=auto_process_next_stage,
        )

    def _generate_blend_file(self):
        logger.debug(
            "Generating `.blend` file (this will freeze the GUI while it is running, sorry! I tried to calculate_center_of_mass it in a thread instead of a 'subprocess' but I got some kind of permission error when it tried to save the `.blend` file, so.... here we are. Frozen in the GUI.  How are you? "
        )
        # self._thread_worker_manager.launch_export_to_blender_thread_worker(
        #     get_session_folder_path(self._session_id)
        # )
        path_to_skeleton_body_csv = get_skeleton_body_csv_path(self._session_id)
        skeleton_dataframe = pd.read_csv(path_to_skeleton_body_csv)

        skeleton_segment_lengths_dict = estimate_skeleton_segment_lengths(
            skeleton_dataframe=skeleton_dataframe,
            skeleton_segment_definitions=mediapipe_skeleton_segment_definitions,
        )

        save_skeleton_segment_lengths_to_json(
            get_output_data_folder_path(self._session_id), skeleton_segment_lengths_dict
        )

        blender_file_path = export_to_blender(
            session_folder_path=get_session_folder_path(self._session_id),
            blender_exe_path=self._control_panel.visualize_session_data_panel.blender_exe_path_str,
        )

        if (
            self._control_panel.process_session_data_panel.open_in_blender_automatically_checkbox.isChecked()
        ):
            if blender_file_path:
                self._open_blender_file(blender_file_path)

    def _open_blender_file(self, blender_file_path: Union[str, Path]):
        logger.info(f"Opening {str(blender_file_path)}")

        if blender_file_path is False:
            blender_file_path = get_blender_file_path(self._session_id)

        if not Path(blender_file_path).exists():
            logger.error(f"ERROR - {str(blender_file_path)} does not exist!")
            return

        os.startfile(str(blender_file_path))

    def _visualize_motion_capture_data(self):
        logger.info("Loading data for visualization...")

        skeleton_3d_npy = load_post_processed_mediapipe3d_data(
            Path(get_output_data_folder_path(self._session_id))
            / PARTIALLY_PROCESSED_DATA_FOLDER_NAME
            / MEDIAPIPE_3D_ORIGIN_ALIGNED_NPY_FILE_NAME
        )

        video_path_iterator = Path(
            get_annotated_videos_folder_path(self._session_id)
        ).glob("*.mp4".lower())
        list_of_video_paths = [str(video_path) for video_path in video_path_iterator]

        dictionary_of_video_image_update_callbacks = (
            self._middle_viewing_panel.dictionary_of_video_image_update_callbacks
        )
        self._middle_viewing_panel.show_session_playback_view(
            mediapipe3d_trackedPoint_xyz=skeleton_3d_npy[0, :, :],
            list_of_video_paths=list_of_video_paths,
        )
        self._thread_worker_manager.launch_session_playback_thread(
            frames_per_second=30,
            list_of_video_paths=list_of_video_paths,
            dictionary_of_video_image_update_callbacks=dictionary_of_video_image_update_callbacks,
            skeleton_3d_npy=skeleton_3d_npy,
            update_3d_skeleton_callback=self._middle_viewing_panel.session_playback_view.update_3d_skeleton_callback,
        )

    def _reboot_gui(self):
        logger.info("Rebooting GUI... ")
        get_qt_app().exit(EXIT_CODE_REBOOT)

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:

        if (
            self._middle_viewing_panel.welcome_create_or_load_session_panel.send_pings_checkbox.isChecked()
        ):
            pipedream_ping_dict = (
                self._thread_worker_manager.session_progress_dictionary
            )
            if Path(get_blender_file_path(self._session_id)).exists():
                pipedream_ping_dict["blender_file_created"] = True
            else:
                pipedream_ping_dict["blender_file_created"] = False
            send_pipedream_ping(pipedream_ping_dict)

        logger.info("Close Event detected for main window... ")
        self._middle_viewing_panel.camera_stream_grid_view.close_camera_widgets()

        if self._session_id is not None:
            session_folder = get_session_folder_path(self._session_id)
            dir = os.listdir(session_folder)
            if len(dir) == 0:
                logger.info(f"{self._session_id} folder is empty, so let's delete it")
                Path(session_folder).rmdir()
                return
            else:
                try:
                    session_log_path = (
                        str(
                            Path(get_session_folder_path(self._session_id))
                            / self._session_id
                        )
                        + "_log.log"
                    )
                    logger.info(
                        f"Trying to copy log file from {LOG_FILE_PATH} as session log file: {session_log_path}..."
                    )
                    shutil.copy2(
                        LOG_FILE_PATH, get_session_folder_path(self._session_id)
                    )
                except Exception as e:
                    logger.error(f"Something went wrong copying the log file")
                    print(e)

    # def _set_icon(self):
    #
    #     icon = QtGui.QIcon()
    #     logo_path = "assets/logo/freemocap-skelly-logo-black-border-white-bkgd.png"
    #     icon.addPixmap(QtGui.QPixmap(logo_path), QtGui.QIcon.Selected, QtGui.QIcon.On)
    #     self.setWindowIcon(icon)
