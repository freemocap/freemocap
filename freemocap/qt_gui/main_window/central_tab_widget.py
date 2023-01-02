from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget
from skellycam import SkellyCamControllerWidget, SkellyCamViewerWidget

from freemocap.qt_gui.widgets.welcome_tab_widget import (
    WelcomeCreateOrLoadNewSessionPanel,
)


class CentralTabWidget(QTabWidget):
    def __init__(
        self,
        camera_view_widget: SkellyCamViewerWidget,
        camera_controller_widget: SkellyCamControllerWidget,
        welcome_to_freemocap_widget: WelcomeCreateOrLoadNewSessionPanel,
        visualize_data_widget,
        parent=None,
    ):

        super().__init__(parent=parent)
        self.parent = parent

        self._camera_view_widget = camera_view_widget
        self._camera_controller_widget = camera_controller_widget
        self._welcome_to_freemocap_widget = welcome_to_freemocap_widget
        self._visualize_data_widget = visualize_data_widget

        self._create_welcome_tab(self)
        self._create_camera_view_tab(self)
        self._create_visualization_tab(self)

    def set_welcome_tab_enabled(self, enabled: bool):
        self.setTabEnabled(0, enabled)

    def set_camera_view_tab_enabled(self, enabled: bool):
        self.setTabEnabled(1, enabled)

    def set_visualize_data_tab_enabled(self, enabled: bool):
        self.setTabEnabled(2, enabled)

    def _create_camera_view_tab(self, tab_widget: QTabWidget):
        dummy_widget = QWidget()
        self._camera_view_layout = QVBoxLayout()
        dummy_widget.setLayout(self._camera_view_layout)
        tab_widget.addTab(dummy_widget, "Record!")

        # self._qt_multi_camera_viewer_widget.resize(1280, 720)

        self._camera_view_layout.addWidget(self._camera_controller_widget)
        self._camera_view_layout.addWidget(self._camera_view_widget)

    def _create_welcome_tab(self, tab_widget: QTabWidget):
        tab_widget.addTab(self._welcome_to_freemocap_widget, "Welcome!")

    def _create_visualization_tab(self, tab_widget: QTabWidget):

        self._visualize_data_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tab_widget.addTab(self._visualize_data_widget, "View!")
