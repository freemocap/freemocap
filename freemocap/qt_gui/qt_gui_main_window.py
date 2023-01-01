import logging
import multiprocessing
from pathlib import Path
from typing import Union

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDockWidget, QLabel, QMainWindow, QVBoxLayout, QWidget
from skellycam import (
    SkellyCamControllerWidget,
    SkellyCamParameterTreeWidget,
    SkellyCamViewerWidget,
)
from skellycam.qt_gui.widgets.qt_directory_view_widget import QtDirectoryViewWidget

from freemocap.default_paths_and_filenames.paths_and_files_names import (
    get_css_stylesheet_path,
)
from freemocap.qt_gui.style_sheet.css_file_watcher import CSSFileWatcher
from freemocap.qt_gui.style_sheet.set_css_style_sheet import apply_css_style_sheet

logger = logging.getLogger(__name__)


class QtGUIMainWindow(QMainWindow):
    def __init__(self, freemocap_data_folder: Union[str, Path] = None, parent=None):
        logger.info("Initializing QtGUIMainWindow")
        super().__init__()
        self.setGeometry(100, 100, 1600, 900)

        self._css_file_watcher = self._set_up_stylesheet()

        self._freemocap_data_folder = freemocap_data_folder
        self.setWindowTitle("freemocap \U0001F480 \U00002728")

        self._central_widget = QWidget()
        self.setCentralWidget(self._central_widget)
        self._layout = QVBoxLayout()
        self._central_widget.setLayout(self._layout)

        self._welcome_to_freemocap_widget = QLabel("Welcome to freemocap!")
        self._layout.addWidget(self._welcome_to_freemocap_widget)

        self._qt_multi_camera_viewer_widget = SkellyCamViewerWidget(parent=self)
        self._qt_multi_camera_viewer_widget.resize(1280, 720)
        self._layout.addWidget(self._qt_multi_camera_viewer_widget)

        self._qt_camera_controller_dock_widget = QDockWidget("Camera Controller", self)
        self._qt_camera_controller_widget = SkellyCamControllerWidget(
            qt_multi_camera_viewer_widget=self._qt_multi_camera_viewer_widget,
            parent=self,
        )
        self._qt_camera_controller_dock_widget.setWidget(
            self._qt_camera_controller_widget
        )
        self.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea,
            self._qt_camera_controller_dock_widget,
        )

        self._parameter_tree_dock_widget = QDockWidget("Camera Settings", self)
        self._parameter_tree_dock_widget.setFloating(False)
        self._qt_camera_config_parameter_tree_widget = SkellyCamParameterTreeWidget()

        # self._layout.addWidget(self._qt_camera_config_parameter_tree_widget)
        self._parameter_tree_dock_widget.setWidget(
            self._qt_camera_config_parameter_tree_widget
        )
        self.addDockWidget(
            Qt.DockWidgetArea.LeftDockWidgetArea, self._parameter_tree_dock_widget
        )

        self._directory_view_dock_widget = QDockWidget("Directory View", self)
        self._qt_directory_view_widget = QtDirectoryViewWidget(
            folder_path=self._freemocap_data_folder
        )
        self._directory_view_dock_widget.setWidget(self._qt_directory_view_widget)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._directory_view_dock_widget
        )

        self._connect_signals_to_slots()

    def _connect_signals_to_slots(self):
        self._qt_multi_camera_viewer_widget.camera_group_created_signal.connect(
            self._qt_camera_config_parameter_tree_widget.update_camera_config_parameter_tree
        )

        self._qt_multi_camera_viewer_widget.camera_group_created_signal.connect(
            self._welcome_to_freemocap_widget.hide
        )

        self._qt_camera_config_parameter_tree_widget.emitting_camera_configs_signal.connect(
            self._qt_multi_camera_viewer_widget.incoming_camera_configs_signal
        )

    def closeEvent(self, a0) -> None:
        try:
            self._qt_multi_camera_viewer_widget.close()
        except Exception as e:
            logger.error(f"Error while closing the viewer widget: {e}")
        super().closeEvent(a0)

    def _set_up_stylesheet(self):
        apply_css_style_sheet(self, get_css_stylesheet_path())

        css_file_watcher = CSSFileWatcher(
            path_to_css_file=get_css_stylesheet_path(), parent=self
        )

        return css_file_watcher


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    main_window = QtGUIMainWindow()
    main_window.show()
    app.exec()
    for process in multiprocessing.active_children():
        logger.info(f"Terminating process: {process}")
        process.terminate()
    sys.exit()
