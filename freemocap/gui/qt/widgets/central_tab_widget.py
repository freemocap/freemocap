import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTabWidget, QVBoxLayout, QWidget
# from skelly_viewer import SkellyViewer
from skellycam import SkellyCamWidget

from freemocap.gui.qt.widgets.welcome_panel_widget import (
    WelcomeToFreemocapPanel,
)
from freemocap.system.paths_and_files_names import CAMERA_WITH_FLASH_EMOJI_STRING, EYES_EMOJI_STRING

logger = logging.getLogger(__name__)


class CentralTabWidget(QTabWidget):
    def __init__(
        self,
        skelly_cam_widget: SkellyCamWidget,
        camera_controller_widget: QWidget,
        welcome_to_freemocap_widget: WelcomeToFreemocapPanel,
        skelly_viewer_widget: QWidget,
        parent=None,
    ):
        super().__init__(parent=parent)
        self.parent = parent

        # self.setTabShape(QTabWidget.TabShape.Triangular)

        self._skelly_cam_widget = skelly_cam_widget
        self._camera_controller_widget = camera_controller_widget
        self._welcome_to_freemocap_widget = welcome_to_freemocap_widget
        self._skelly_viewer_widget = skelly_viewer_widget

        self._create_welcome_tab(self)
        self._create_skellycam_view_tab(self)
        self._create_skelly_viewer_tab(self)

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
        tab_widget.addTab(dummy_widget, f"Skelly Cam")
        # tab_widget.setToolTip(skellycam.__repo_url__)

        # self._qt_multi_camera_viewer_widget.resize(1280, 720)
        self._camera_view_layout.addWidget(self._camera_controller_widget)

        self._camera_view_layout.addWidget(self._skelly_cam_widget)

    def _create_skelly_viewer_tab(self, tab_widget: QTabWidget):
        logger.info("Creating export_data tab")
        tab_widget.addTab(self._skelly_viewer_widget, f"Skelly Viewer")
        # tab_widget.setToolTip(skelly_viewer.__repo_url__)
