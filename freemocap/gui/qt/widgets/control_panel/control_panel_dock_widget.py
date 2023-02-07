from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDockWidget,
    QVBoxLayout,
    QWidget,
    QToolBox,
)
from skellycam import SkellyCamParameterTreeWidget

from freemocap.gui.qt.widgets.control_panel.calibration_control_panel import (
    CalibrationControlPanel,
)
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
        return self._control_panel_widget.tool_box


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

        self._tool_box = QToolBox(parent=self)
        self._layout.addWidget(self._tool_box)

        self._tool_box.addItem(camera_configuration_parameter_tree_widget, "Camera Configuration")
        # self._tool_box.addItem(calibration_control_panel, "Capture Volume Calibration")
        self._tool_box.addItem(process_motion_capture_data_panel, "Process Motion Capture Data")
        self._tool_box.addItem(visualize_data_widget, "Visualize Motion Capture Data")

        self._tool_box.setProperty("disabled_appearance", True)
        self.style().polish(self._tool_box)

    @property
    def tool_box(self):
        return self._tool_box

    def set_up_tool_box_appearance(self):
        self._tool_box.setProperty("disabled_appearance", False)
        self.style().polish(self._tool_box)
