import logging
import multiprocessing
import shutil
import threading
from copy import copy
from pathlib import Path
from typing import Union

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDockWidget,
    QMainWindow,
    QFileDialog,
    QTabWidget,
)
from skelly_viewer import SkellyViewer
from skellycam import (
    SkellyCamParameterTreeWidget,
    SkellyCamWidget,
    SkellyCamControllerWidget,
)

from freemocap.core_processes.export_data.blender_stuff.export_to_blender import (
    export_to_blender,
)
from freemocap.core_processes.export_data.blender_stuff.get_best_guess_of_blender_path import \
    get_best_guess_of_blender_path
from freemocap.gui.qt.actions_and_menus.actions import Actions
from freemocap.gui.qt.actions_and_menus.menu_bar import MenuBar
from freemocap.gui.qt.style_sheet.css_file_watcher import CSSFileWatcher
from freemocap.gui.qt.style_sheet.set_css_style_sheet import apply_css_style_sheet
from freemocap.gui.qt.utilities.get_qt_app import get_qt_app
from freemocap.gui.qt.utilities.save_most_recent_recording_path_as_toml import (
    save_most_recent_recording_path_as_toml,
)
from freemocap.gui.qt.widgets.active_recording_widget import ActiveRecordingInfoWidget
from freemocap.gui.qt.widgets.camera_controller_group_box import CameraControllerGroupBox
from freemocap.gui.qt.widgets.central_tab_widget import CentralTabWidget
from freemocap.gui.qt.widgets.control_panel.control_panel_dock_widget import (
    ControlPanelWidget,
)
from freemocap.gui.qt.widgets.control_panel.process_mocap_data_panel.process_motion_capture_data_panel import (
    ProcessMotionCaptureDataPanel,
)
from freemocap.gui.qt.widgets.control_panel.visualization_control_panel import VisualizationControlPanel
from freemocap.gui.qt.widgets.directory_view_widget import DirectoryViewWidget
from freemocap.gui.qt.widgets.log_view_widget import LogViewWidget
from freemocap.gui.qt.widgets.welcome_panel_widget import (
    WelcomeToFreemocapPanel,
)
from freemocap.parameter_info_models.recording_info_model import (
    RecordingInfoModel,
)
from freemocap.parameter_info_models.recording_processing_parameter_models import (
    RecordingProcessingParameterModel,
)
from freemocap.system.paths_and_files_names import (
    get_css_stylesheet_path,
    get_freemocap_data_folder_path,
    get_most_recent_recording_path,
    PATH_TO_FREEMOCAP_LOGO_SVG,
    get_blender_file_path,
    get_recording_session_folder_path,
    DIRECTORY_EMOJI_STRING,
    GEAR_EMOJI_STRING,
    COOL_EMOJI_STRING,
)

# reboot GUI method based on this - https://stackoverflow.com/a/56563926/14662833
from freemocap.system.start_file import open_file

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

        self.setGeometry(100, 100, 1280, 720)
        self.setWindowIcon(QIcon(PATH_TO_FREEMOCAP_LOGO_SVG))
        self.setWindowTitle("freemocap \U0001F480 \U00002728")

        self._css_file_watcher = self._set_up_stylesheet()

        if freemocap_data_folder_path is None:
            self._freemocap_data_folder_path = get_freemocap_data_folder_path()
        else:
            self._freemocap_data_folder_path = freemocap_data_folder_path

        self._kill_thread_event = threading.Event()

        self._active_recording_info_widget = ActiveRecordingInfoWidget(parent=self)
        self._active_recording_info_widget.new_active_recording_selected_signal.connect(
            self._handle_new_active_recording_selected
        )
        self._directory_view_widget = self._create_directory_view_widget()
        self._directory_view_widget.expand_directory_to_path(get_recording_session_folder_path())
        self._directory_view_widget.new_active_recording_selected_signal.connect(
            self._active_recording_info_widget.set_active_recording
        )

        self._actions = Actions(freemocap_main_window=self)

        self._menu_bar = MenuBar(actions=self._actions, parent=self)
        self.setMenuBar(self._menu_bar)

        self._central_tab_widget = self._create_central_tab_widget()
        self.setCentralWidget(self._central_tab_widget)

        self._tools_dock_widget = self._create_tools_dock_widget()
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._tools_dock_widget)
        self._tools_dock_tab_widget = QTabWidget(self)
        self._tools_dock_widget.setWidget(self._tools_dock_tab_widget)

        self._control_panel_dock_widget = self._create_control_panel_widget()
        self._tools_dock_tab_widget.addTab(self._control_panel_dock_widget, f"Control Panel{GEAR_EMOJI_STRING}")

        self._tools_dock_tab_widget.addTab(self._directory_view_widget, f"Directory View{DIRECTORY_EMOJI_STRING}")
        self._tools_dock_tab_widget.addTab(
            self._active_recording_info_widget, f"Active Recording Info{COOL_EMOJI_STRING}"
        )

        # self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._directory_view_dock_widget)

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

    def _create_tools_dock_widget(self):
        tools_dock_widget = QDockWidget("Tools and Info", self)
        tools_dock_widget.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        tools_dock_widget.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        return tools_dock_widget

    def _handle_videos_saved_to_this_folder_signal(self, folder_path: str):
        save_most_recent_recording_path_as_toml(most_recent_recording_path=folder_path)
        self._directory_view_widget.expand_directory_to_path(directory_path=folder_path)
        self._active_recording_info_widget.set_active_recording(recording_folder_path=folder_path)

        if (
            self._controller_group_box.auto_process_videos_checked
            and self._controller_group_box.mocap_videos_radio_button_checked
        ):
            logger.info("'Auto process videos' checkbox is checked - triggering 'Process Motion Capture Data' button")
            self._process_motion_capture_data_panel.process_motion_capture_data_button.click()
        elif self._controller_group_box.calibration_videos_radio_button_checked:
            logger.info("Processing calibration videos")
            self._process_motion_capture_data_panel.calibrate_from_active_recording(
                charuco_square_size_mm=float(self._controller_group_box.charuco_square_size)
            )

    def _handle_processing_finished_signal(self):
        logger.info("Processing finished")
        if self._controller_group_box.auto_process_videos_checked:
            logger.info("'Auto process videos' checkbox is checked - triggering 'Create Blender Scene'")
            self._handle_export_to_blender_button_clicked()

    def handle_start_new_session_action(self):
        # self._central_tab_widget.set_welcome_tab_enabled(True)
        self._central_tab_widget.set_camera_view_tab_enabled(True)
        self._central_tab_widget.setCurrentIndex(1)
        self._controller_group_box.show()
        self._skellycam_widget.detect_available_cameras()

    def update(self):
        super().update()
        if not self._skellycam_widget.is_recording:
            self._controller_group_box.update_recording_name_string()

    def _set_up_stylesheet(self):
        apply_css_style_sheet(self, get_css_stylesheet_path())
        css_file_watcher = CSSFileWatcher(path_to_css_file=get_css_stylesheet_path(), parent=self)
        return css_file_watcher

    def _create_new_synchronized_videos_folder(self) -> str:
        new_recording_folder_path = self._controller_group_box.get_new_recording_path()
        logger.info(f"Creating new recording folder at: {new_recording_folder_path}")
        self._active_recording_info_widget.set_active_recording(recording_folder_path=new_recording_folder_path)
        return self._active_recording_info_widget.active_recording_info.synchronized_videos_folder_path

    def _create_central_tab_widget(self):

        self._welcome_to_freemocap_widget = WelcomeToFreemocapPanel(actions=self._actions, parent=self)

        self._skellycam_widget = SkellyCamWidget(
            parent=self, get_new_synchronized_videos_folder_callable=self._create_new_synchronized_videos_folder
        )
        self._skellycam_widget.videos_saved_to_this_folder_signal.connect(
            self._handle_videos_saved_to_this_folder_signal
        )

        self._skellycam_controller_widget = SkellyCamControllerWidget(
            camera_viewer_widget=self._skellycam_widget,
            parent=self,
        )

        self._controller_group_box = CameraControllerGroupBox(
            skellycam_controller=self._skellycam_controller_widget, parent=self
        )

        self._skelly_viewer_widget = SkellyViewer()

        center_tab_widget = CentralTabWidget(
            parent=self,
            skelly_cam_widget=self._skellycam_widget,
            camera_controller_widget=self._controller_group_box,
            welcome_to_freemocap_widget=self._welcome_to_freemocap_widget,
            skelly_viewer_widget=self._skelly_viewer_widget,
        )

        center_tab_widget.set_welcome_tab_enabled(True)
        center_tab_widget.set_camera_view_tab_enabled(True)
        center_tab_widget.set_visualize_data_tab_enabled(True)

        return center_tab_widget

    def _create_directory_view_widget(self):
        return DirectoryViewWidget(
            top_level_folder_path=self._freemocap_data_folder_path,
            get_active_recording_info_callable=self._active_recording_info_widget.get_active_recording_info,
        )

    def _create_directory_view_dock_widget(self):
        directory_view_dock_widget = QDockWidget("Directory View", self)
        self._directory_view_widget = self._create_directory_view_widget()
        directory_view_dock_widget.setWidget(self._directory_view_widget)

        return directory_view_dock_widget

    # def _create_tool_bar(self):
    #     self._calibration_control_panel = CalibrationControlPanel(
    #         get_active_recording_info_callable=self._active_recording_info_widget.get_active_recording_info,
    #     )
    #     self._process_motion_capture_data_panel = ProcessMotionCaptureDataPanel(
    #         recording_processing_parameters=RecordingProcessingParameterModel(),
    #         get_active_recording_info=self._active_recording_info_widget.get_active_recording_info,
    #     )
    #     self._process_motion_capture_data_panel.processing_finished_signal.connect(
    #         self._handle_processing_finished_signal
    #     )
    #     return ToolBar(calibration_control_panel=self._calibration_control_panel,
    #                    process_motion_capture_data_panel=self._process_motion_capture_data_panel,
    #                    visualize_data_widget=self._create_visualization_control_panel(),
    #                    directory_view_widget=self._create_directory_view_widget(),
    #                    parent=self)

    def _create_control_panel_widget(self):

        self._camera_configuration_parameter_tree_widget = SkellyCamParameterTreeWidget(self._skellycam_widget)

        # self._calibration_control_panel = CalibrationControlPanel(
        #     get_active_recording_info_callable=self._active_recording_info_widget.get_active_recording_info,
        # )

        self._process_motion_capture_data_panel = ProcessMotionCaptureDataPanel(
            recording_processing_parameters=RecordingProcessingParameterModel(),
            get_active_recording_info=self._active_recording_info_widget.get_active_recording_info,
            kill_thread_event=self._kill_thread_event,
        )
        self._process_motion_capture_data_panel.processing_finished_signal.connect(
            self._handle_processing_finished_signal
        )

        self._visualization_control_panel = VisualizationControlPanel(parent=self,
                                                                      blender_executable=get_best_guess_of_blender_path())
        self._visualization_control_panel.export_to_blender_button.clicked.connect(
            self._handle_export_to_blender_button_clicked
        )

        return ControlPanelWidget(
            camera_configuration_parameter_tree_widget=self._camera_configuration_parameter_tree_widget,
            # calibration_control_panel=self._calibration_control_panel,
            process_motion_capture_data_panel=self._process_motion_capture_data_panel,
            visualize_data_widget=self._visualization_control_panel,
            parent=self,
        )

    def _handle_export_to_blender_button_clicked(self):
        recording_path = self._active_recording_info_widget.get_active_recording_info(return_path=True)

        self._visualization_control_panel.get_user_selected_method_string()
        export_to_blender(
            recording_folder_path=recording_path,
            blender_file_path=get_blender_file_path(recording_path),
            blender_exe_path=self._visualization_control_panel.blender_executable,
            method=self._visualization_control_panel.get_user_selected_method_string(),
        )

        if (
            self._controller_group_box.auto_open_in_blender_checked
            or self._visualization_control_panel.open_in_blender_automatically_box_is_checked
        ):
            open_file(self._active_recording_info_widget.active_recording_info.blender_file_path)

    def _handle_new_active_recording_selected(self, recording_info_model: RecordingInfoModel):
        logger.info(f"New active recording selected: {recording_info_model.path}")

        # self._calibration_control_panel.update_calibrate_from_active_recording_button_text()

        self._directory_view_widget.set_folder_as_root(Path(recording_info_model.path).parent)
        if Path(recording_info_model.synchronized_videos_folder_path).exists():
            self._directory_view_widget.expand_directory_to_path(recording_info_model.synchronized_videos_folder_path)
        else:
            self._directory_view_widget.expand_directory_to_path(recording_info_model.path)

        self._active_recording_info_widget.update_parameter_tree()
        # self._recording_name_label.setText(f"Recording Name: {recording_info_model.name}")
        # self._update_skelly_viewer_widget()
        self._directory_view_widget.handle_new_active_recording_selected()

    def _update_skelly_viewer_widget(self):
        active_recording_info = self._active_recording_info_widget.active_recording_info

        if active_recording_info is None:
            self._central_tab_widget.set_visualize_data_tab_enabled(False)
            return

        if active_recording_info.data3d_status_check:
            self._skelly_viewer_widget.load_skeleton_data(
                mediapipe_skeleton_npy_path=active_recording_info.mediapipe_3d_data_npy_file_path
            )
            self._central_tab_widget.set_visualize_data_tab_enabled(True)

        if active_recording_info.data2d_status_check:
            self._skelly_viewer_widget.generate_video_display(
                video_folder_path=active_recording_info.annotated_videos_folder_path
            )
            self._central_tab_widget.set_visualize_data_tab_enabled(True)

        elif active_recording_info.synchronized_videos_status_check:
            self._skelly_viewer_widget.generate_video_display(
                video_folder_path=active_recording_info.synchronized_videos_folder_path
            )
            self._central_tab_widget.set_visualize_data_tab_enabled(True)

    def reboot_gui(self):
        logger.info("Rebooting GUI... ")
        get_qt_app().exit(EXIT_CODE_REBOOT)

    def kill_running_threads_and_processes(self):
        logger.info("Killing running threads and processes... ")
        try:
            self._skellycam_widget.close()
        except Exception as e:
            logger.error(f"Error killing running threads and processes: {e}")

        self._kill_thread_event.set()
        self._old_kill_event = copy(self._kill_thread_event)

    def handle_load_most_recent_recording(self):
        logger.info("`Load Most Recent Recording` QAction triggered")
        most_recent_recording_path = get_most_recent_recording_path()

        if most_recent_recording_path is None:
            logger.error(f"`get_most_recent_recording_path()` return `None`!")
            return

        self._active_recording_info_widget.set_active_recording(recording_folder_path=get_most_recent_recording_path())
        self._central_tab_widget.setCurrentIndex(2)
        self._control_panel_dock_widget.tab_widget.setCurrentWidget(self._process_motion_capture_data_panel)

    def open_load_existing_recording_dialog(self):
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

    def open_import_videos_dialog(self):
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

        synchronized_videos_folder_path = self._create_new_synchronized_videos_folder()
        Path(synchronized_videos_folder_path).mkdir(parents=True, exist_ok=True)

        logger.info(f"Copying videos from {external_videos_path} to {synchronized_videos_folder_path}")

        for video_path in Path(external_videos_path).glob("*.mp4"):
            logger.debug(f"Copying {video_path}...")

            shutil.copy(video_path, synchronized_videos_folder_path)

    def closeEvent(self, a0) -> None:
        logger.info("Main window `closeEvent` detected")
        remove_empty_directories(get_recording_session_folder_path())

        try:
            self._skellycam_widget.close()
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
