import logging
import multiprocessing
import shutil
from pathlib import Path
from typing import Union

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDockWidget,
    QMainWindow,
    QPushButton,
    QFileDialog,
    QGroupBox,
    QVBoxLayout,
    QLabel,
    QCheckBox,
    QHBoxLayout,
    QLineEdit,
    QFormLayout,
    QGridLayout,
    QRadioButton,
    QSpacerItem,
    QSizePolicy,
)

# from skelly_viewer import SkellyViewer
from skellycam import (
    SkellyCamParameterTreeWidget,
    SkellyCamWidget,
    SkellyCamControllerWidget,
)

from freemocap.core_processes.capture_volume_calibration.charuco_stuff.default_charuco_square_size import (
    default_charuco_square_size_mm,
)
from freemocap.system.paths_and_files_names import (
    get_css_stylesheet_path,
    get_freemocap_data_folder_path,
    get_most_recent_recording_path,
    PATH_TO_FREEMOCAP_LOGO_SVG,
    RECORDING_SESSIONS_FOLDER_NAME,
    create_new_recording_folder_path,
    get_blender_file_path,
    get_recording_session_folder_path,
    create_new_default_recording_name,
)
from freemocap.core_processes.visualization.blender_stuff.export_to_blender import (
    export_to_blender,
)
from freemocap.gui.qt.actions_and_menu_bar.actions import Actions
from freemocap.gui.qt.actions_and_menu_bar.menu_bar import (
    MenuBar,
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
from freemocap.gui.qt.widgets.welcome_panel_widget import (
    WelcomeToFreemocapPanel,
)
from freemocap.parameter_info_models.recording_info_model import (
    RecordingInfoModel,
)
from freemocap.parameter_info_models.recording_processing_parameter_models import (
    RecordingProcessingParameterModel,
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
        self.setGeometry(100, 100, 1600, 900)
        self.setWindowIcon(QIcon(PATH_TO_FREEMOCAP_LOGO_SVG))
        self.setWindowTitle("freemocap \U0001F480 \U00002728")

        self._css_file_watcher = self._set_up_stylesheet()

        self._active_recording_info_widget = ActiveRecordingInfoWidget(parent=self)
        self._active_recording_info_widget.new_active_recording_selected_signal.connect(
            self._handle_new_active_recording_selected
        )

        self._actions = Actions(freemocap_main_window=self)
        self._menu_bar = MenuBar(actions=self._actions, parent=self)
        self.setMenuBar(self._menu_bar)

        if freemocap_data_folder_path is None:
            self._freemocap_data_folder_path = get_freemocap_data_folder_path()
        else:
            self._freemocap_data_folder_path = freemocap_data_folder_path

        self._central_tab_widget = self._create_central_tab_widget()
        self.setCentralWidget(self._central_tab_widget)

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

    def _handle_videos_saved_to_this_folder_signal(self, folder_path: str):
        save_most_recent_recording_path_as_toml(most_recent_recording_path=folder_path)
        self._directory_view_widget.expand_directory_to_path(directory_path=folder_path)
        self._active_recording_info_widget.set_active_recording(recording_folder_path=folder_path)

        if self._auto_process_videos_checkbox.isChecked() and self._mocap_videos_radio_button.isChecked():
            logger.info("'Auto process videos' checkbox is checked - triggering 'Process Motion Capture Data' button")
            self._process_motion_capture_data_panel.process_motion_capture_data_button.click()
        elif self._calibration_videos_radio_button.isChecked():
            logger.info("Processing calibration videos")
            self._calibration_control_panel.calibrate_from_active_recording(
                charuco_square_size_mm=float(self._charuco_square_size_line_edit.text())
            )

    def _handle_processing_finished_signal(self):
        logger.info("Processing finished")
        if self._auto_process_videos_checkbox.isChecked():
            logger.info("'Auto process videos' checkbox is checked - triggering 'Create Blender Scene'")
            self._handle_export_to_blender_button_clicked()

    def handle_start_new_session_action(self):
        # self._central_tab_widget.set_welcome_tab_enabled(True)
        self._central_tab_widget.set_camera_view_tab_enabled(True)
        self._central_tab_widget.setCurrentIndex(1)
        self._controller_group_box.show()
        self._skellycam_widget.detect_available_cameras()

    def update(self):
        self._update_recording_name_string()

    def _update_recording_name_string(self):
        self._recording_path_label.setText(create_new_recording_folder_path(recording_name=self._get_recording_name()))

    def _set_up_stylesheet(self):
        apply_css_style_sheet(self, get_css_stylesheet_path())
        css_file_watcher = CSSFileWatcher(path_to_css_file=get_css_stylesheet_path(), parent=self)
        return css_file_watcher

    def _get_recording_name_string_tag(self):
        try:
            tag = self._recording_string_tag_line_edit.text()
            tag = tag.replace("   ", " ")
            tag = tag.replace("  ", " ")
            tag = tag.replace(" ", "_")
            return tag
        except:
            return ""

    def _get_recording_name(self):
        tag = self._get_recording_name_string_tag()
        if tag == "":
            return create_new_default_recording_name()
        else:
            return f"{create_new_default_recording_name()}_{self._get_recording_name_string_tag()}"

    def _create_new_synchronized_videos_folder(self) -> str:
        new_recording_folder_path = create_new_recording_folder_path(recording_name=self._get_recording_name())
        # logger.info(f"Creating new recording folder at: {new_recording_folder_path}")
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

        self._controller_group_box = QGroupBox("")

        # self._controller_group_box.setFlat(True)
        controller_layout = QVBoxLayout()
        self._controller_group_box.setLayout(controller_layout)

        # controller_layout.setContentsMargins(0, 0, 0, 0)
        # controller_layout.setSpacing(0)
        controller_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._camera_controller_widget = SkellyCamControllerWidget(
            camera_viewer_widget=self._skellycam_widget,
            parent=self,
        )
        controller_layout.addWidget(self._camera_controller_widget)

        self._recording_name_controller_row_layout = QHBoxLayout()
        controller_layout.addLayout(self._recording_name_controller_row_layout)

        self._recording_string_tag_line_edit = QLineEdit(parent=self)
        self._recording_string_tag_line_edit.setPlaceholderText("(Optional)")
        # self._recording_string_tag_line_edit.setFixedWidth(300)
        recording_string_tag_form_layout = QFormLayout(parent=self)
        recording_string_tag_form_layout.addRow("Recording Name Tag", self._recording_string_tag_line_edit)
        self._recording_name_controller_row_layout.addLayout(recording_string_tag_form_layout)

        hbox = QHBoxLayout()
        hbox.setAlignment(Qt.AlignmentFlag.AlignLeft)
        hbox.addWidget(QLabel("Videos will save to folder: "))
        self._recording_path_label = QLabel(f"{create_new_recording_folder_path(self._get_recording_name())}")
        self._recording_path_label.setStyleSheet("font-family: monospace;")
        hbox.addWidget(self._recording_path_label)
        # self._recording_path_label.setStyleSheet("font-family: monospace; font-size: 12px; font-weight: bold;")
        controller_layout.addLayout(hbox)

        recording_type_radio_button_layout = QVBoxLayout()
        controller_layout.addLayout(recording_type_radio_button_layout)

        record_motion_capture_videos_layout = QHBoxLayout()
        record_motion_capture_videos_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._mocap_videos_radio_button = QRadioButton("Record Motion Capture Videos")
        record_motion_capture_videos_layout.addWidget(self._mocap_videos_radio_button)
        self._mocap_videos_radio_button.setChecked(True)

        record_motion_capture_videos_layout.addWidget(QLabel(" - "))

        self._auto_process_videos_checkbox = QCheckBox("Auto Process Videos on Save")
        self._auto_process_videos_checkbox.setChecked(True)
        record_motion_capture_videos_layout.addWidget(self._auto_process_videos_checkbox)

        self._auto_open_in_blender_checkbox = QCheckBox("Auto Open in Blender")
        self._auto_open_in_blender_checkbox.setChecked(True)
        record_motion_capture_videos_layout.addWidget(self._auto_open_in_blender_checkbox)
        controller_layout.addLayout(record_motion_capture_videos_layout)

        record_calibration_videos_layout = QHBoxLayout()
        record_calibration_videos_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        record_calibration_videos_layout.setSizeConstraint(record_motion_capture_videos_layout.sizeConstraint())
        self._calibration_videos_radio_button = QRadioButton("Record Calibration Videos")
        record_calibration_videos_layout.addWidget(self._calibration_videos_radio_button)
        record_calibration_videos_layout.addWidget(QLabel(" - "))

        charuco_square_size_form_layout = QFormLayout(parent=self)
        record_calibration_videos_layout.addLayout(charuco_square_size_form_layout)
        self._charuco_square_size_line_edit = QLineEdit(parent=self)
        self._charuco_square_size_line_edit.setFixedWidth(100)
        self._charuco_square_size_label = QLabel("Charuco square size (mm)")
        self._charuco_square_size_line_edit.setText(str(default_charuco_square_size_mm))
        self._charuco_square_size_line_edit.setToolTip(
            "The length of one of the edges of the black squares in the calibration board in mm"
        )
        charuco_square_size_form_layout.addRow(self._charuco_square_size_label, self._charuco_square_size_line_edit)

        controller_layout.addLayout(record_calibration_videos_layout)

        self._skelly_viewer_widget = QLabel("Hello, just imagine this was `skelly_viewer` lol")  # SkellyViewer()

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

    def _create_directory_view_dock_widget(self):
        directory_view_dock_widget = QDockWidget("Directory View", self)
        self._directory_view_widget = DirectoryViewWidget(top_level_folder_path=self._freemocap_data_folder_path)
        self._directory_view_widget.set_path_as_index(self._freemocap_data_folder_path)
        self._directory_view_widget.expand_directory_to_path(
            Path(self._freemocap_data_folder_path) / RECORDING_SESSIONS_FOLDER_NAME
        )

        directory_view_dock_widget.setWidget(self._directory_view_widget)

        return directory_view_dock_widget

    def _create_control_panel_dock_widget(self):
        self._camera_configuration_parameter_tree_widget = SkellyCamParameterTreeWidget(self._skellycam_widget)
        self._calibration_control_panel = CalibrationControlPanel(
            get_active_recording_info_callable=self._active_recording_info_widget.get_active_recording_info,
        )
        self._process_motion_capture_data_panel = ProcessMotionCaptureDataPanel(
            recording_processing_parameters=RecordingProcessingParameterModel(),
            get_active_recording_info=self._active_recording_info_widget.get_active_recording_info,
        )
        self._process_motion_capture_data_panel.processing_finished_signal.connect(
            self._handle_processing_finished_signal
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
        if self._auto_open_in_blender_checkbox.isChecked():
            open_file(self._active_recording_info_widget.active_recording_info.blender_file_path)

    def _handle_new_active_recording_selected(self, recording_info_model: RecordingInfoModel):
        logger.info(f"New active recording selected: {recording_info_model.path}")

        # self._calibration_control_panel.update_calibrate_from_active_recording_button_text()

        self._active_recording_dock_widget.setWindowTitle(f"Active Recording: {recording_info_model.name}")

        if Path(recording_info_model.synchronized_videos_folder_path).exists():
            self._directory_view_widget.expand_directory_to_path(recording_info_model.synchronized_videos_folder_path)
        else:
            self._directory_view_widget.expand_directory_to_path(recording_info_model.path)

        self._active_recording_info_widget.update_parameter_tree()
        # self._recording_name_label.setText(f"Recording Name: {recording_info_model.name}")

    def reboot_gui(self):
        logger.info("Rebooting GUI... ")
        get_qt_app().exit(EXIT_CODE_REBOOT)

    def load_most_recent_recording(self):
        logger.info("`Load Most Recent Recording` QAction triggered")
        most_recent_recording_path = get_most_recent_recording_path()

        if most_recent_recording_path is None:
            logger.error(f"`get_most_recent_recording_path()` return `None`!")
            return

        self._active_recording_info_widget.set_active_recording(recording_folder_path=get_most_recent_recording_path())
        self._central_tab_widget.setCurrentIndex(2)

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
