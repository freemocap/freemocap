from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDockWidget,
    QLabel,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from skellycam import SkellyCamParameterTreeWidget

from freemocap.gui.qt.widgets.control_panel.calibration_control_panel import (
    CalibrationControlPanel,
)
from freemocap.gui.qt.widgets.control_panel.process_mocap_data_panel.process_motion_capture_data_panel import (
    ProcessMotionCaptureDataPanel,
)


class ControlPanelDockWidget(QDockWidget):
    def __init__(
        self,
        camera_configuration_parameter_tree_widget: SkellyCamParameterTreeWidget,
        calibration_control_panel: CalibrationControlPanel,
        process_motion_capture_data_panel: ProcessMotionCaptureDataPanel,
        visualize_data_widget: QWidget,
        parent=None,
    ):
        super().__init__(parent=parent)

        self._splitter = QSplitter()
        self._splitter.setOrientation(Qt.Orientation.Vertical)
        self.setWidget(self._splitter)

        self._add_widget_to_splitter(
            widget=camera_configuration_parameter_tree_widget,
            title_str="Camera Configuration",
        )

        self._add_widget_to_splitter(
            widget=calibration_control_panel,
            title_str="Capture Volume Calibration",
        )

        self._add_widget_to_splitter(
            widget=process_motion_capture_data_panel,
            title_str="Process Motion Capture Data",
        )

        self._add_widget_to_splitter(
            widget=visualize_data_widget,
            title_str="Visualize Motion Capture Data",
            add_stretch=True,
        )

    def _add_widget_to_splitter(self, widget: QWidget, title_str: str, add_stretch: bool = False):
        dummy_widget = QWidget()
        layout = QVBoxLayout()
        dummy_widget.setLayout(layout)
        layout.addWidget(self._create_section_title(title=title_str))
        layout.addWidget(widget)
        if add_stretch:
            layout.addStretch()

        self._splitter.addWidget(dummy_widget)

    def _create_section_title(self, title: str):
        label = QLabel(title)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setAlignment(Qt.AlignmentFlag.AlignTop)
        label.setStyleSheet("font-size: 20px; font-weight: bold;")
        return label
