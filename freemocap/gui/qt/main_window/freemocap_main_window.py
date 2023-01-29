import logging
import multiprocessing
from pathlib import Path
from typing import Union

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QDockWidget, QLabel, QMainWindow, QPushButton
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
)
from freemocap.core_processes.session_processing_parameter_models.session_processing_parameter_models import (
    SessionProcessingParameterModel,
)
from freemocap.core_processes.session_processing_parameter_models.session_recording_info.recording_info_model import (
    RecordingInfoModel,
)
from freemocap.core_processes.visualization.blender_stuff.export_to_blender import (
    export_to_blender,
)
from freemocap.gui.qt.main_window.menu_bar import (
    LOAD_MOST_RECENT_SESSION_ACTION_NAME,
    MenuBar,
)
from freemocap.gui.qt.style_sheet.css_file_watcher import CSSFileWatcher
from freemocap.gui.qt.style_sheet.set_css_style_sheet import apply_css_style_sheet
from freemocap.gui.qt.utilities.save_most_recent_recording_path_as_toml import (
    save_most_recent_recording_path_as_toml,
)
from freemocap.gui.qt.widgets.active_recording_widget import ActiveRecordingWidget
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

        self._menu_bar = MenuBar(self)
        self.setMenuBar(self._menu_bar)

        self._active_recording_info = None

        self._session_process_parameter_model = SessionProcessingParameterModel(
            recording_info_model=self._active_recording_info,
        )

        if freemocap_data_folder_path is None:
            self._freemocap_data_folder_path = get_freemocap_data_folder_path()
        else:
            self._freemocap_data_folder_path = freemocap_data_folder_path

        self.setWindowTitle("freemocap \U0001F480 \U00002728")

        self._active_recording_widget = ActiveRecordingWidget(self._active_recording_info, parent=self)

        self._central_tab_widget = self._create_center_tab_widget()
        self.setCentralWidget(self._central_tab_widget)

        self._active_recording_dock_widget = QDockWidget("Active Recording", self)
        self._active_recording_dock_widget.setWidget(self._active_recording_widget.active_recording_view_widget)
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
        self._welcome_to_freemocap_widget.quick_start_button.clicked.connect(self._handle_quick_start_button_clicked)

        self._skellycam_view_widget.videos_saved_to_this_folder_signal.connect(
            self._handle_videos_saved_to_this_folder_signal
        )

        self._active_recording_widget.new_active_recording_selected_signal.connect(
            self._handle_new_active_recording_selected
        )

        self._menu_bar.actions_dictionary[LOAD_MOST_RECENT_SESSION_ACTION_NAME].triggered.connect(
            lambda: self._active_recording_widget.set_active_recording(
                recording_folder_path=get_most_recent_recording_path()
            )
        )

    def _handle_videos_saved_to_this_folder_signal(self, folder_path: str):
        save_most_recent_recording_path_as_toml(most_recent_recording_path=folder_path)
        self._directory_view_widget.expand_directory_to_path(directory_path=folder_path)
        self._active_recording_widget.set_active_recording(recording_folder_path=folder_path)

    def _handle_quick_start_button_clicked(self):
        self._central_tab_widget.set_welcome_tab_enabled(False)
        self._central_tab_widget.set_camera_view_tab_enabled(True)
        self._central_tab_widget.setCurrentIndex(1)

        self._skellycam_view_widget.detect_available_cameras()

    def _set_up_stylesheet(self):
        apply_css_style_sheet(self, get_css_stylesheet_path())

        css_file_watcher = CSSFileWatcher(path_to_css_file=get_css_stylesheet_path(), parent=self)

        return css_file_watcher

    def _create_center_tab_widget(self):
        self._skellycam_view_widget = SkellyCamViewerWidget(
            parent=self,
            get_new_synchronized_videos_folder_callable=self._active_recording_widget.get_synchronized_videos_folder_path,
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
            get_active_recording_info_callable=self._active_recording_widget.get_active_recording_info,
        )
        self._process_motion_capture_data_panel = ProcessMotionCaptureDataPanel(
            session_processing_parameters=self._session_process_parameter_model,
            get_active_recording_info=self._active_recording_widget.get_active_recording_info,
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
        self._export_to_blender_button.clicked.connect(lambda: export_to_blender(get_most_recent_recording_path()))
        return self._export_to_blender_button

    def _create_directory_view_dock_widget(self):
        directory_view_dock_widget = QDockWidget("Directory View", self)
        self._directory_view_widget = DirectoryViewWidget(top_level_folder_path=self._freemocap_data_folder_path)
        self._directory_view_widget.set_path_as_index(self._freemocap_data_folder_path)
        self._directory_view_widget.expand_directory_to_path(
            Path(self._freemocap_data_folder_path) / RECORDING_SESSIONS_FOLDER_NAME
        )

        directory_view_dock_widget.setWidget(self._directory_view_widget)

        return directory_view_dock_widget

    def closeEvent(self, a0) -> None:
        remove_empty_directories(get_freemocap_data_folder_path())

        try:
            self._skellycam_view_widget.close()
        except Exception as e:
            logger.error(f"Error while closing the viewer widget: {e}")
        super().closeEvent(a0)

    def _handle_new_active_recording_selected(self, recording_info_model: RecordingInfoModel):
        logger.info(f"New active recording selected: {recording_info_model.path}")

        self._calibration_control_panel.set_active_recording_folder_path_label(recording_info_model.path)

        self._active_recording_dock_widget.setWindowTitle(f"Active Recording: {recording_info_model.name}")

        if Path(recording_info_model.synchronized_videos_folder_path).exists():
            self._directory_view_widget.expand_directory_to_path(recording_info_model.synchronized_videos_folder_path)
        else:
            self._directory_view_widget.expand_directory_to_path(recording_info_model.path)


def remove_empty_directories(root_dir: Union[str, Path]):
    """
    Recursively remove empty directories from the root directory
    :param root_dir: The root directory to start removing empty directories from
    """
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
