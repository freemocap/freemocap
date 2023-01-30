import logging
import multiprocessing
import shutil
from pathlib import Path
from typing import Union

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import QDockWidget, QLabel, QMainWindow, QPushButton, QFileDialog, QMenu, QMenuBar
from skellycam import (
    SkellyCamControllerWidget,
    SkellyCamParameterTreeWidget,
    SkellyCamViewerWidget,
)

from freemocap.configuration.paths_and_files_names import (
    get_css_stylesheet_path,
    get_freemocap_data_folder_path,
    get_most_recent_recording_path,
    PATH_TO_FREEMOCAP_LOGO_SVG,
    RECORDING_SESSIONS_FOLDER_NAME,
    create_new_recording_folder_path,
    get_blender_file_path,
    get_recording_session_folder_path,
)
from freemocap.core_processes.visualization.blender_stuff.export_to_blender import (
    export_to_blender,
)
from freemocap.gui.qt.actions_and_menu_bar.menu_bar import (
    LOAD_MOST_RECENT_RECORDING_ACTION_NAME,
    LOAD_EXISTING_RECORDING_ACTION_NAME,
    IMPORT_VIDEOS_ACTION_NAME,
    CREATE_NEW_RECORDING_ACTION_NAME,
)
from freemocap.gui.qt.style_sheet.css_file_watcher import CSSFileWatcher
from freemocap.gui.qt.style_sheet.set_css_style_sheet import apply_css_style_sheet
from freemocap.gui.qt.utilities.get_qt_app import get_qt_app
from freemocap.gui.qt.utilities.save_most_recent_recording_path_as_toml import (
    save_most_recent_recording_path_as_toml,
)
from freemocap.gui.qt.widgets.active_recording_widget import ActiveRecordingInfoWidget
from freemocap.gui.qt.widgets.central_tab_widget import CentralTabWidget
from freemocap.gui.qt.widgets.control_panel.calibration_control_panel import (
    CalibrationControlPanel,
)
from freemocap.gui.qt.widgets.control_panel.control_panel_dock_widget import (
    ControlPanelDockWidget,
)
from freemocap.gui.qt.widgets.directory_view_widget import DirectoryViewWidget
from freemocap.gui.qt.widgets.log_view_widget import LogViewWidget
from freemocap.gui.qt.widgets.process_mocap_data_panel.process_motion_capture_data_panel import (
    ProcessMotionCaptureDataPanel,
)
from freemocap.gui.qt.widgets.welcome_tab_widget import (
    WelcomeCreateOrLoadNewSessionPanel,
)
from freemocap.parameter_info_models.recording_info_model import (
    RecordingInfoModel,
)
from freemocap.parameter_info_models.session_processing_parameter_models import (
    SessionProcessingParameterModel,
)

# reboot GUI method based on this - https://stackoverflow.com/a/56563926/14662833
EXIT_CODE_REBOOT = -123456789

logger = logging.getLogger(__name__)


class FreemocapMainWindow(QMainWindow):
    def __init__(
        self,
        freemocap_data_folder_path: Union[str, Path] = None,
        parent=None,
    ):

        logger.info("Initializing QtGUIMainWindow")
        super().__init__(parent=parent)
        self.setGeometry(100, 100, 1600, 900)
        self.setWindowIcon(QIcon(PATH_TO_FREEMOCAP_LOGO_SVG))
        self._css_file_watcher = self._set_up_stylesheet()

        self._central_tab_widget = self._create_central_tab_widget()
        self.setCentralWidget(self._central_tab_widget)

        self._create_actions()
        self._create_menu_bar()

        self._active_recording_info = None

        self._session_process_parameter_model = SessionProcessingParameterModel(
            recording_info_model=self._active_recording_info,
        )

        if freemocap_data_folder_path is None:
            self._freemocap_data_folder_path = get_freemocap_data_folder_path()
        else:
            self._freemocap_data_folder_path = freemocap_data_folder_path

        self.setWindowTitle("freemocap \U0001F480 \U00002728")

        self._active_recording_info_widget = ActiveRecordingInfoWidget(self._active_recording_info, parent=self)

        self._active_recording_dock_widget = QDockWidget("Active Recording", self)
        self._active_recording_dock_widget.setWidget(self._active_recording_info_widget.active_recording_view_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._active_recording_dock_widget)

        self._control_panel_dock_widget = self._create_control_panel_dock_widget()
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._control_panel_dock_widget)

        self._directory_view_dock_widget = self._create_directory_view_dock_widget()
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._directory_view_dock_widget)

        # self._jupyter_console_widget = JupyterConsoleWidget(parent=self)
        # jupyter_console_dock_widget = QDockWidget("Jupyter IPython Console", self)
        # self.addDockWidget(
        #     Qt.DockWidgetArea.BottomDockWidgetArea, jupyter_console_dock_widget
        # )
        # jupyter_console_dock_widget.setWidget(self._jupyter_console_widget)

        self._log_view_widget = LogViewWidget(parent=self)
        log_view_dock_widget = QDockWidget("Log View", self)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, log_view_dock_widget)
        log_view_dock_widget.setWidget(self._log_view_widget)

        self._connect_signals_to_slots()

    def _connect_signals_to_slots(self):
        self._welcome_to_freemocap_widget.quick_start_button.clicked.connect(self._create_new_recording_action.trigger)

        self._skellycam_view_widget.videos_saved_to_this_folder_signal.connect(
            self._handle_videos_saved_to_this_folder_signal
        )

        self._active_recording_info_widget.new_active_recording_selected_signal.connect(
            self._handle_new_active_recording_selected
        )

    def _handle_videos_saved_to_this_folder_signal(self, folder_path: str):
        save_most_recent_recording_path_as_toml(most_recent_recording_path=folder_path)
        self._directory_view_widget.expand_directory_to_path(directory_path=folder_path)
        self._active_recording_info_widget.set_active_recording(recording_folder_path=folder_path)

    def _handle_start_new_session_action(self):
        # self._central_tab_widget.set_welcome_tab_enabled(True)
        self._central_tab_widget.set_camera_view_tab_enabled(True)
        self._central_tab_widget.setCurrentIndex(1)

        # self._skellycam_view_widget.detect_available_cameras()

    def _set_up_stylesheet(self):
        apply_css_style_sheet(self, get_css_stylesheet_path())

        css_file_watcher = CSSFileWatcher(path_to_css_file=get_css_stylesheet_path(), parent=self)

        return css_file_watcher

    def _create_new_synchronized_videos_folder(self) -> str:

        new_recording_folder_path = create_new_recording_folder_path()
        logger.info(f"Creating new recording folder at: {new_recording_folder_path}")
        self._active_recording_info_widget.set_active_recording(recording_folder_path=new_recording_folder_path)

        return self._active_recording_info_widget.active_recording_info.synchronized_videos_folder_path

    def _create_central_tab_widget(self):
        self._skellycam_view_widget = SkellyCamViewerWidget(
            parent=self, get_new_synchronized_videos_folder_callable=self._create_new_synchronized_videos_folder
        )
        self._camera_controller_widget = SkellyCamControllerWidget(
            camera_viewer_widget=self._skellycam_view_widget,
            parent=self,
        )

        self._welcome_to_freemocap_widget = WelcomeCreateOrLoadNewSessionPanel()
        self._visualize_data_widget = QLabel("Visualize Data")

        center_tab_widget = CentralTabWidget(
            parent=self,
            camera_view_widget=self._skellycam_view_widget,
            camera_controller_widget=self._camera_controller_widget,
            welcome_to_freemocap_widget=self._welcome_to_freemocap_widget,
            visualize_data_widget=self._visualize_data_widget,
        )

        center_tab_widget.set_welcome_tab_enabled(True)
        center_tab_widget.set_camera_view_tab_enabled(False)
        center_tab_widget.set_visualize_data_tab_enabled(False)

        return center_tab_widget

    def _create_control_panel_dock_widget(self):
        self._camera_configuration_parameter_tree_widget = SkellyCamParameterTreeWidget(self._skellycam_view_widget)
        self._calibration_control_panel = CalibrationControlPanel(
            get_active_recording_info_callable=self._active_recording_info_widget.get_active_recording_info,
        )
        self._process_motion_capture_data_panel = ProcessMotionCaptureDataPanel(
            session_processing_parameters=self._session_process_parameter_model,
            get_active_recording_info=self._active_recording_info_widget.get_active_recording_info,
        )

        control_panel_dock_widget = ControlPanelDockWidget(
            camera_configuration_parameter_tree_widget=self._camera_configuration_parameter_tree_widget,
            calibration_control_panel=self._calibration_control_panel,
            process_motion_capture_data_panel=self._process_motion_capture_data_panel,
            visualize_data_widget=self._create_visualization_control_panel(),
            parent=self,
        )

        return control_panel_dock_widget

    def _create_visualization_control_panel(self):
        self._export_to_blender_button = QPushButton("Export to Blender")
        self._export_to_blender_button.clicked.connect(self._handle_export_to_blender_button_clicked)
        return self._export_to_blender_button

    def _handle_export_to_blender_button_clicked(self):
        recording_path = self._active_recording_info_widget.get_active_recording_info(return_path=True)
        export_to_blender(recording_folder_path=recording_path, blender_file_path=get_blender_file_path(recording_path))

    def _create_directory_view_dock_widget(self):
        directory_view_dock_widget = QDockWidget("Directory View", self)
        self._directory_view_widget = DirectoryViewWidget(top_level_folder_path=self._freemocap_data_folder_path)
        self._directory_view_widget.set_path_as_index(self._freemocap_data_folder_path)
        self._directory_view_widget.expand_directory_to_path(
            Path(self._freemocap_data_folder_path) / RECORDING_SESSIONS_FOLDER_NAME
        )

        directory_view_dock_widget.setWidget(self._directory_view_widget)

        return directory_view_dock_widget

    def _handle_new_active_recording_selected(self, recording_info_model: RecordingInfoModel):
        logger.info(f"New active recording selected: {recording_info_model.path}")

        self._calibration_control_panel.update_calibrate_from_active_recording_button_text()

        self._active_recording_dock_widget.setWindowTitle(f"Active Recording: {recording_info_model.name}")

        if Path(recording_info_model.synchronized_videos_folder_path).exists():
            self._directory_view_widget.expand_directory_to_path(recording_info_model.synchronized_videos_folder_path)
        else:
            self._directory_view_widget.expand_directory_to_path(recording_info_model.path)

    def _create_actions(self):

        # File
        self._create_new_recording_action = QAction(CREATE_NEW_RECORDING_ACTION_NAME, parent=self)
        self._create_new_recording_action.setShortcut("Ctrl+N")
        self._create_new_recording_action.triggered.connect(self._handle_start_new_session_action)

        self._load_most_recent_session_action = QAction(LOAD_MOST_RECENT_RECORDING_ACTION_NAME, parent=self)
        self._load_most_recent_session_action.setShortcut("Ctrl+D")
        self._load_most_recent_session_action.triggered.connect(self._handle_load_most_recent_session_action_triggered)

        self._import_videos_action = QAction(IMPORT_VIDEOS_ACTION_NAME, parent=self)
        self._import_videos_action.setShortcut("Ctrl+I")
        self._import_videos_action.triggered.connect(self._open_import_videos_dialog)

        self._reboot_gui_action = QAction("&Reboot GUI", parent=self)
        self._reboot_gui_action.setShortcut("Ctrl+R")
        self._reboot_gui_action.triggered.connect(self._reboot_gui)

        self._load_session_action = QAction(LOAD_EXISTING_RECORDING_ACTION_NAME, parent=self)
        self._load_session_action.setShortcut("Ctrl+O")
        self._load_session_action.triggered.connect(self._open_load_existing_recording_dialog)

        self._exit_action = QAction("E&xit", parent=self)
        self._exit_action.setShortcut("Ctrl+Q")
        self._exit_action.triggered.connect(self.close)

        # Help
        self._open_docs_action = QAction("Open  &Documentation", parent=self)
        self._about_us_action = QAction("&About Us", parent=self)

        # Navigation
        self._show_camera_control_panel_action = QAction("&1 - Show Camera Control Panel", parent=self)
        self._show_camera_control_panel_action.setShortcut("Ctrl+1")

        self._show_calibrate_capture_volume_panel_action = QAction(
            "&2 - Show Calibrate Capture Volume Panel", parent=self
        )
        self._show_calibrate_capture_volume_panel_action.setShortcut("Ctrl+2")

        self._show_motion_capture_videos_panel_action = QAction("&3 - Show Motion Capture Videos Panel", parent=self)
        self._show_motion_capture_videos_panel_action.setShortcut("Ctrl+3")

        # Support
        self._donate_action = QAction("&Donate", parent=self)
        self._send_usage_statistics_action = QAction("Send &User Statistics", parent=self)
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

        file_menu.addAction(self._create_new_recording_action)
        file_menu.addAction(self._load_most_recent_session_action)
        file_menu.addAction(self._load_session_action)
        file_menu.addAction(self._import_videos_action)
        file_menu.addAction(self._reboot_gui_action)
        file_menu.addAction(self._exit_action)
        #
        # # navigation menu
        # navigation_menu = QMenu("Na&vigation", parent=menu_bar)
        # menu_bar.addMenu(navigation_menu)
        # navigation_menu.addAction(self._show_camera_control_panel_action)
        # navigation_menu.addAction(self._show_calibrate_capture_volume_panel_action)
        # navigation_menu.addAction(self._show_motion_capture_videos_panel_action)
        #
        # # help menu
        # help_menu = QMenu("&Help", parent=menu_bar)
        # menu_bar.addMenu(help_menu)
        # help_menu.setEnabled(False)
        #
        # help_menu.addAction(self._open_docs_action)
        # help_menu.addAction(self._about_us_action)
        #
        # # support menu
        # support_menu = QMenu(
        #     "\U00002665 &Support the FreeMoCap Project", parent=menu_bar
        # )
        # support_menu.setEnabled(False)
        # menu_bar.addMenu(support_menu)
        #
        # support_menu.addAction(self._donate_action)
        # support_menu.addAction(self._send_usage_statistics_action)
        # support_menu.addAction(self._user_survey_action)

    def _reboot_gui(self):
        logger.info("Rebooting GUI... ")
        get_qt_app().exit(EXIT_CODE_REBOOT)

    def _handle_load_most_recent_session_action_triggered(self):
        logger.info("`Load Most Recent Recording` QAction triggered")
        most_recent_recording_path = get_most_recent_recording_path()

        if most_recent_recording_path is None:
            logger.error(f"`get_most_recent_recording_path()` return `None`!")
            return

        self._active_recording_info_widget.set_active_recording(recording_folder_path=get_most_recent_recording_path())

    def _open_load_existing_recording_dialog(self):
        # from this tutorial - https://www.youtube.com/watch?v=gg5TepTc2Jg&t=649s
        logger.info("Opening `Load Existing Recording` dialog... ")
        user_selected_directory = QFileDialog.getExistingDirectory(
            self,
            "Select a recording folder",
            str(get_recording_session_folder_path()),
        )
        if len(user_selected_directory) == 0:
            logger.info("User cancelled `Load Existing Recording` dialog")
            return

        user_selected_directory = user_selected_directory[0]
        logger.info(f"User selected recording path:{user_selected_directory}")

        self._active_recording_info_widget.set_active_recording(recording_folder_path=user_selected_directory)

    def _open_import_videos_dialog(self):
        # from this tutorial - https://www.youtube.com/watch?v=gg5TepTc2Jg&t=649s
        logger.info("Opening `Import Videos` dialog... ")
        external_videos_path = QFileDialog.getExistingDirectory(
            self,
            "Select a folder containing synchronized videos (each video must have *exactly* the same number of frames)",
            str(Path.home()),
        )

        if len(external_videos_path) == 0:
            logger.info("User cancelled `Import Videos` dialog")
            return

        self._active_recording_info_widget.set_active_recording(
            recording_folder_path=create_new_recording_folder_path()
        )

        synchronized_videos_folder_path = (
            self._active_recording_info_widget.active_recording_info.synchronized_videos_folder_path
        )

        logger.info(f"Copying videos from {external_videos_path} to {synchronized_videos_folder_path}")

        for video_path in Path(external_videos_path).glob("*.mp4"):
            logger.debug(f"Copying {video_path}...")
            shutil.copy(video_path, synchronized_videos_folder_path)

    def closeEvent(self, a0) -> None:
        logger.info("Main window `closeEvent` detected")
        remove_empty_directories(get_recording_session_folder_path())

        try:
            self._skellycam_view_widget.close()
        except Exception as e:
            logger.error(f"Error while closing the viewer widget: {e}")
        super().closeEvent(a0)


def remove_empty_directories(root_dir: Union[str, Path]):
    """
    Recursively remove empty directories from the root directory
    :param root_dir: The root directory to start removing empty directories from
    """
    # logger.debug(f"Searching for empty directories in: {root_dir}")
    for path in Path(root_dir).rglob("*"):
        if path.is_dir() and not any(path.iterdir()):
            logger.info(f"Removing empty directory: {path}")
            path.rmdir()
        elif path.is_dir() and any(path.iterdir()):
            remove_empty_directories(path)
        else:
            continue


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    main_window = FreemocapMainWindow()
    main_window.show()
    app.exec()
    for process in multiprocessing.active_children():
        logger.info(f"Terminating process: {process}")
        process.terminate()
    sys.exit()
