from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDockWidget,
    QVBoxLayout,
    QWidget,
    QTabWidget,
)
from skellycam import SkellyCamParameterTreeWidget

from freemocap.gui.qt.widgets.control_panel.process_mocap_data_panel.process_motion_capture_data_panel import (
    ProcessMotionCaptureDataPanel,
)


class ControlPanelDockWidget(QDockWidget):
    def __init__(self, **kwargs):
        super().__init__("Control", parent=kwargs.get("parent"))

        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable)

        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)

        self._control_panel_widget = ControlPanelWidget(**kwargs)
        self.setWidget(self._control_panel_widget)

    @property
    def tool_box(self):
        return self._control_panel_widget.tab_widget


class ControlPanelWidget(QWidget):
    def __init__(
        self,
        camera_configuration_parameter_tree_widget: SkellyCamParameterTreeWidget,
        # calibration_control_panel: CalibrationControlPanel,
        process_motion_capture_data_panel: ProcessMotionCaptureDataPanel,
        visualize_data_widget: QWidget,
        parent=None,
    ):
        super().__init__(parent=parent)

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._tab_widget = QTabWidget(parent=self)
        self._layout.addWidget(self._tab_widget)

        self._tab_widget.addTab(
            camera_configuration_parameter_tree_widget,
            "Camera Configuration",
        )
        # self._tool_box.addTab(calibration_control_panel, "Capture Volume Calibration")
        self._tab_widget.addTab(process_motion_capture_data_panel, "Process Data")
        self._tab_widget.addTab(visualize_data_widget, "Export Data")

        self._tab_widget.setProperty("control_panel_tabs", True)
        self.style().polish(self._tab_widget)

    @property
    def tab_widget(self):
        return self._tab_widget
