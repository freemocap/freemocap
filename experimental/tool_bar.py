from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QToolBar, QWidget

from freemocap.gui.qt.widgets.control_panel.calibration_control_panel import CalibrationControlPanel
from freemocap.gui.qt.widgets.control_panel.process_mocap_data_panel.process_motion_capture_data_panel import (
    ProcessMotionCaptureDataPanel,
)


class ToolBar(QToolBar):
    def __init__(
        self,
        calibration_control_panel: CalibrationControlPanel,
        process_motion_capture_data_panel: ProcessMotionCaptureDataPanel,
        visualize_data_widget: QWidget,
        directory_view_widget: QWidget,
        parent=None,
    ):
        super().__init__(parent=parent)

        self._calibration_control_panel = calibration_control_panel
        self._process_motion_capture_data_panel = process_motion_capture_data_panel
        self._visualize_data_widget = visualize_data_widget
        self._directory_view_widget = directory_view_widget

        self.setMovable(True)
        self.setFloatable(True)
        self.setAllowedAreas(Qt.ToolBarArea.AllToolBarAreas)

        self._create_toolbar_actions()
        self._create_tool_bar()

    def _create_tool_bar(self):
        self.addAction(self._open_directory_action)

    def _create_toolbar_actions(self):
        self._open_directory_action = self.addAction("Open Directory")
        self._open_directory_action.triggered.connect(self._open_directory_widget)

    def _open_directory_widget(self):
        self._directory_view_widget.show()

        # self._directory_view_dock_widget.raise_()
        # self._directory_view_dock_widget.activateWindow()
