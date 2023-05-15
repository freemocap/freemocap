import logging
import multiprocessing
import shutil
from pathlib import Path
from typing import Union, List

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDockWidget,
    QMainWindow,
    QFileDialog,
    QTabWidget, QWidget, QHBoxLayout, )
from skelly_viewer import SkellyViewer
from skellycam import (
    SkellyCamParameterTreeWidget,
    SkellyCamWidget,
    SkellyCamControllerWidget,
)
from tqdm import tqdm

from freemocap.core_processes.export_data.blender_stuff.export_to_blender import (
    export_to_blender,
)
from freemocap.core_processes.export_data.blender_stuff.get_best_guess_of_blender_path import \
    get_best_guess_of_blender_path
from freemocap.gui.qt.actions_and_menus.actions import Actions
from freemocap.gui.qt.actions_and_menus.menu_bar import MenuBar
from freemocap.gui.qt.style_sheet.css_file_watcher import CSSFileWatcher
from freemocap.gui.qt.style_sheet.scss_file_watcher import SCSSFileWatcher
from freemocap.gui.qt.style_sheet.set_css_style_sheet import apply_css_style_sheet
from freemocap.gui.qt.utilities.get_qt_app import get_qt_app
from freemocap.gui.qt.utilities.update_most_recent_recording_toml import (
    update_most_recent_recording_toml,
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
from freemocap.gui.qt.widgets.import_videos_window import ImportVideosWizard
from freemocap.gui.qt.widgets.log_view_widget import LogViewWidget
from freemocap.gui.qt.widgets.home_widget import (
    HomeWidget,
)
from freemocap.parameter_info_models.recording_info_model import (
    RecordingInfoModel,
)
from freemocap.parameter_info_models.recording_processing_parameter_models import (
    RecordingProcessingParameterModel,
)
from freemocap.system.paths_and_files_names import (
    get_scss_stylesheet_path,
    get_css_stylesheet_path,
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
from freemocap.system.user_data.pipedream_pings import PipedreamPings

EXIT_CODE_REBOOT = -123456789

logger = logging.getLogger(__name__)


class FreemocapMainWindow(QMainWindow):
    def __init__(
            self,
            freemocap_data_folder_path: Union[str, Path],
            pipedream_pings: PipedreamPings,
            parent=None,
    ):

        logger.info("Initializing QtGUIMainWindow")
        super().__init__(parent=parent)

        self.setGeometry(100, 100, 1280, 720)
        self.setWindowIcon(QIcon(PATH_TO_FREEMOCAP_LOGO_SVG))
        self.setWindowTitle("freemocap \U0001F480 \U00002728")

        dummy_widget = QWidget()
        self._layout = QHBoxLayout()
        dummy_widget.setLayout(self._layout)
        self.setCentralWidget(dummy_widget)

        self._css_file_watcher = self._set_up_stylesheet()

        self._freemocap_data_folder_path = freemocap_data_folder_path
        self._pipedream_pings = pipedream_pings

        self._kill_thread_event = multiprocessing.Event()

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

        self.statusBar().showMessage(
            "Watch the terminal output for status updates, we're working on integrating better status updates into the GUI")

        self._central_tab_widget = self._create_central_tab_widget()
        self.setCentralWidget(self._central_tab_widget)

        self._tools_dock_widget = self._create_tools_dock_widget()
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._tools_dock_widget)
        # self._tools_dock_tab_widget = QTabWidget(self)

        self._control_panel_widget = self._create_control_panel_widget()
        self._tools_dock_widget.setWidget(self._control_panel_widget)
        # self._tools_dock_tab_widget.addTab(self._control_panel_widget, f"Control Panel")
        #
        # self._tools_dock_tab_widget.addTab(self._directory_view_widget, f"Directory View")
        # self._tools_dock_tab_widget.addTab(
        #     self._active_recording_info_widget, f"Active Recording Info"
        # )

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
        log_view_dock_widget.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )

    def _create_tools_dock_widget(self):
        tools_dock_widget = QDockWidget("Control Panel", self)
        tools_dock_widget.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        tools_dock_widget.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        return tools_dock_widget

    def _handle_videos_saved_to_this_folder_signal(self, folder_path: str):
        logger.info(f"Videos saved to this folder signal received: {folder_path}")

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
        if self._controller_group_box.auto_open_in_blender_checked and not self._kill_thread_event.is_set():
            logger.info("'Auto process videos' checkbox is checked - triggering 'Create Blender Scene'")
            self._export_active_recording_to_blender()

    def handle_start_new_session_action(self):
        # self._central_tab_widget.set_welcome_tab_enabled(True)
        self._central_tab_widget.set_camera_view_tab_enabled(True)
        self._central_tab_widget.setCurrentIndex(1)
        self._controller_group_box.show()
        self._skellycam_widget.detect_available_cameras()

    def update(self):
        super().update()

        try:
            if not self._skellycam_widget.is_recording:
                self._controller_group_box.update_recording_name_string()
        except Exception as e:
            logger.exception(e)

    def _set_up_stylesheet(self):
        apply_css_style_sheet(self, get_css_stylesheet_path())
        scss_file_watcher = SCSSFileWatcher(path_to_scss_file=get_scss_stylesheet_path(), path_to_css_file=get_css_stylesheet_path(), parent=self)
        css_file_watcher = CSSFileWatcher(path_to_css_file=get_css_stylesheet_path(), parent=self)
        return css_file_watcher

    def _create_new_synchronized_videos_folder(self) -> str:
        new_recording_folder_path = self._controller_group_box.get_new_recording_path()
        logger.info(f"Creating new recording folder at: {new_recording_folder_path}")
        self._active_recording_info_widget.set_active_recording(recording_folder_path=new_recording_folder_path)
        return self._active_recording_info_widget.active_recording_info.synchronized_videos_folder_path

    def _create_central_tab_widget(self):

        self._home_widget = HomeWidget(actions=self._actions, parent=self)

        self._skellycam_widget = SkellyCamWidget(
            self._create_new_synchronized_videos_folder,
            parent=self,
        )
        self._skellycam_widget.videos_saved_to_this_folder_signal.connect(
            self._handle_videos_saved_to_this_folder_signal
        )

        self._skellycam_controller_widget = SkellyCamControllerWidget(
            self._skellycam_widget,
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
            welcome_to_freemocap_widget=self._home_widget,
            skelly_viewer_widget=self._skelly_viewer_widget,
            directory_view_widget=self._directory_view_widget,
            active_recording_info_widget=self._active_recording_info_widget
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
                                                                      blender_executable_path=get_best_guess_of_blender_path())
        self._visualization_control_panel.export_to_blender_button.clicked.connect(
            self._export_active_recording_to_blender
        )

        return ControlPanelWidget(
            camera_configuration_parameter_tree_widget=self._camera_configuration_parameter_tree_widget,
            # calibration_control_panel=self._calibration_control_panel,
            process_motion_capture_data_panel=self._process_motion_capture_data_panel,
            visualize_data_widget=self._visualization_control_panel,
            parent=self,
        )

    def _export_active_recording_to_blender(self):
        logger.info("Exporting active recording to Blender...")
        recording_path = self._active_recording_info_widget.get_active_recording_info(return_path=True)

        if self._visualization_control_panel.blender_executable_path is None:
            logger.error("Blender executable path is None!")
            return

        self._visualization_control_panel.get_user_selected_method_string()
        export_to_blender(
            recording_folder_path=recording_path,
            blender_file_path=get_blender_file_path(recording_path),
            blender_exe_path=self._visualization_control_panel.blender_executable_path,
            method=self._visualization_control_panel.get_user_selected_method_string(),
        )

        if (
                self._controller_group_box.auto_open_in_blender_checked
                # or self._visualization_control_panel.open_in_blender_automatically_box_is_checked
        ):
            if Path(self._active_recording_info_widget.active_recording_info.blender_file_path).exists():
                open_file(self._active_recording_info_widget.active_recording_info.blender_file_path)
            else:
                logger.error("Blender file does not exist! Did something go wrong in the `export_to_blender` call above?")

    def _handle_new_active_recording_selected(self, recording_info_model: RecordingInfoModel):
        logger.info(f"New active recording selected: {recording_info_model.path}")

        # self._calibration_control_panel.update_calibrate_from_active_recording_button_text()
        self._pipedream_pings.update_pings_dict(key=recording_info_model.name,
                                                value=self._active_recording_info_widget.active_recording_info.status_check)

        path = Path(recording_info_model.path)
        path.mkdir(parents=True, exist_ok=True)

        if str(path.parent) != get_recording_session_folder_path():
            self._directory_view_widget.set_folder_as_root(path.parent)
        else:
            self._directory_view_widget.set_folder_as_root(path)

        if Path(recording_info_model.synchronized_videos_folder_path).exists():
            self._directory_view_widget.expand_directory_to_path(recording_info_model.synchronized_videos_folder_path)
        else:
            self._directory_view_widget.expand_directory_to_path(recording_info_model.path)

        self._active_recording_info_widget.update_parameter_tree()
        # self._recording_name_label.setText(f"Recording Name: {recording_info_model.name}")
        self._update_skelly_viewer_widget()
        self._directory_view_widget.handle_new_active_recording_selected()

        try:
            self._process_motion_capture_data_panel.update_calibration_path()
        except Exception as e:
            logger.error(e)



        update_most_recent_recording_toml(recording_info_model=recording_info_model)

    def _update_skelly_viewer_widget(self):
        active_recording_info = self._active_recording_info_widget.active_recording_info


        if active_recording_info.data3d_status_check:
            self._skelly_viewer_widget.load_skeleton_data(
                mediapipe_skeleton_npy_path=active_recording_info.mediapipe_3d_data_npy_file_path
            )


        if active_recording_info.data2d_status_check:
            self._skelly_viewer_widget.generate_video_display(
                video_folder_path=active_recording_info.annotated_videos_folder_path
            )


        elif active_recording_info.synchronized_videos_status_check:
            self._skelly_viewer_widget.generate_video_display(
                video_folder_path=active_recording_info.synchronized_videos_folder_path
            )


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

    def handle_load_most_recent_recording(self):
        logger.info("`Load Most Recent Recording` QAction triggered")
        most_recent_recording_path = get_most_recent_recording_path()

        if most_recent_recording_path is None:
            logger.error(f"`get_most_recent_recording_path()` return `None`!")
            return

        self._active_recording_info_widget.set_active_recording(recording_folder_path=get_most_recent_recording_path())
        self._central_tab_widget.setCurrentIndex(2)
        self._control_panel_widget.tab_widget.setCurrentWidget(self._process_motion_capture_data_panel)

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

        logger.info(f"User selected recording path:{user_selected_directory}")

        self._active_recording_info_widget.set_active_recording(recording_folder_path=user_selected_directory)
        self._central_tab_widget.setCurrentIndex(2)

    def open_import_videos_dialog(self):
        # from this tutorial - https://www.youtube.com/watch?v=gg5TepTc2Jg&t=649s
        logger.info("Opening `Import Videos` dialog... ")

        import_videos_path = QFileDialog.getExistingDirectory(
            self,
            "Select a folder containing synchronized videos (each video must have *exactly* the same number of frames)",
            str(Path.home()),
        )

        if len(import_videos_path) == 0:
            logger.info("User cancelled `Import Videos` dialog")
            return

        self._import_videos_window = ImportVideosWizard(parent=self,
                                                        import_videos_path=import_videos_path,
                                                        )
        self._import_videos_window.folder_to_save_videos_to_selected.connect(self._handle_import_videos)
        text = self._import_videos_window.exec()


    @pyqtSlot(list, str)
    def _handle_import_videos(self, video_paths: List[str], folder_to_save_videos: str):

        folder_to_save_videos = Path(folder_to_save_videos)
        folder_to_save_videos.mkdir(parents=True, exist_ok=True)

        if len(video_paths) == 0:
            logger.error("No videos to import!")
            return

        for video_path in tqdm(video_paths,
                               desc="Importing videos...",
                               colour=[255, 128, 0],
                               unit="video",
                               unit_scale=True,
                               leave=False
                               ):

            if not Path(video_path).exists():
                logger.error(f"{video_path} does not exist!")
                return

            destination_path = folder_to_save_videos / Path(video_path).name
            logger.info(f"Copying video from {video_path} to {destination_path}")

            shutil.copy(video_path, destination_path)

        self._active_recording_info_widget.set_active_recording(
            recording_folder_path=Path(folder_to_save_videos).parent)

    def closeEvent(self, a0) -> None:
        logger.info("Main window `closeEvent` detected")

        self._pipedream_pings.update_pings_dict(key="gui_closed", value=True)
        self._pipedream_pings.update_pings_dict(key="active recording status on close",
                                                value=self._active_recording_info_widget.active_recording_info.status_check)
        self._pipedream_pings.send_pipedream_ping()

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
    main_window = FreemocapMainWindow(pipedream_pings=PipedreamPings())
    main_window.show()
    app.exec()
    for process in multiprocessing.active_children():
        logger.info(f"Terminating process: {process}")
        process.terminate()
    sys.exit()
