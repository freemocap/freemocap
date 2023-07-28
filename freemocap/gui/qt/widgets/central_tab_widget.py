import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTabWidget, QVBoxLayout, QWidget, QLabel

# from skelly_viewer import SkellyViewer
from skellycam import SkellyCamWidget

from freemocap.gui.qt.widgets.home_widget import (
    HomeWidget,
)

logger = logging.getLogger(__name__)


class CentralTabWidget(QTabWidget):
    def __init__(
        self,
        skelly_cam_widget: SkellyCamWidget,
        camera_controller_widget: QWidget,
        welcome_to_freemocap_widget: HomeWidget,
        skelly_viewer_widget: QWidget,
        directory_view_widget: QWidget,
        active_recording_info_widget: QWidget,
        parent=None,
    ):
        super().__init__(parent=parent)
        self.parent = parent

        # self.setTabShape(QTabWidget.TabShape.Triangular)

        self._skelly_cam_widget = skelly_cam_widget
        self._camera_controller_widget = camera_controller_widget
        self._welcome_to_freemocap_widget = welcome_to_freemocap_widget
        self._skelly_viewer_widget = skelly_viewer_widget
        self._directory_view_widget = directory_view_widget
        self._active_recording_info_widget = active_recording_info_widget

        self._create_welcome_tab(self)
        self._create_skellycam_view_tab(self)
        self._create_skelly_viewer_tab(self)
        self._create_directory_view_tab(self)
        self._create_active_recording_info_tab(self)

    def set_welcome_tab_enabled(self, enabled: bool):
        self.setTabEnabled(0, enabled)

    def set_camera_view_tab_enabled(self, enabled: bool):
        self.setTabEnabled(1, enabled)

    def set_visualize_data_tab_enabled(self, enabled: bool):
        self.setTabEnabled(2, enabled)

    def _create_welcome_tab(self, tab_widget: QTabWidget):
        logger.info("Creating welcome tab")
        tab_widget.addTab(self._welcome_to_freemocap_widget, "Home")

    def _create_skellycam_view_tab(self, tab_widget: QTabWidget):
        logger.info("Creating skellycam view tab")
        dummy_widget = QWidget()
        self._camera_view_layout = QVBoxLayout()
        self._camera_view_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        dummy_widget.setLayout(self._camera_view_layout)
        tab_widget.addTab(dummy_widget, "Cameras")
        # tab_widget.setToolTip(skellycam.__repo_url__)

        # self._qt_multi_camera_viewer_widget.resize(1280, 720)
        self._camera_view_layout.addWidget(self._camera_controller_widget)

        self._camera_view_layout.addWidget(self._skelly_cam_widget)

        lag_note_label = QLabel(
            "NOTE: If you experience lag in your camera views, decrease the resolution and/or use fewer cameras. The frames are likely being being recorded properly, its just the viewer that is lagging. A fix is incoming soon!"
        )
        lag_note_label.setStyleSheet("font-size: 10px;")
        lag_note_label.setWordWrap(True)
        layout = QVBoxLayout()
        layout.addWidget(lag_note_label)
        layout.setAlignment(Qt.AlignmentFlag.AlignBottom)
        self._camera_view_layout.addLayout(layout)

    def _create_skelly_viewer_tab(self, tab_widget: QTabWidget):
        logger.info("Creating export_data tab")
        tab_widget.addTab(self._skelly_viewer_widget, "Data Viewer")
        # tab_widget.setToolTip(skelly_viewer.__repo_url__)

    def _create_directory_view_tab(self, tab_widget: QTabWidget):
        logger.info("Creating directory view tab")
        tab_widget.addTab(self._directory_view_widget, "Directory View")

    def _create_active_recording_info_tab(self, tab_widget: QTabWidget):
        logger.info("Creating active recording info tab")
        tab_widget.addTab(self._active_recording_info_widget, "Active Recording Info")
