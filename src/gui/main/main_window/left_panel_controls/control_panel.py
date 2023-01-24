import logging

from PyQt6.QtWidgets import QFrame, QToolBox, QVBoxLayout

from src.gui.main.main_window.left_panel_controls.toolbox_widgets.calibrate_capture_volume_panel import (
    CalibrateCaptureVolumePanel,
)
from src.gui.main.main_window.left_panel_controls.toolbox_widgets.camera_setup_control_panel import (
    CameraSetupControlPanel,
)
from src.gui.main.main_window.left_panel_controls.toolbox_widgets.motion_capture_panel import (
    MotionCapturePanel,
)

logger = logging.getLogger(__name__)

panel_title_strings = {
    "cameras": "1 - Camera Setup and Control",
    "calibration": "2 - Capture Volume Calibration",
    "mocap": "3 - Record/Process/Visualize Motion Capture Data",
}


class ControlPanel:
    def __init__(self):
        self._frame = QFrame()
        self._frame.setFrameShape(QFrame.Shape.StyledPanel)
        self._layout = QVBoxLayout()
        self._frame.setLayout(self._layout)

        self._dictionary_of_toolbox_panels = self._create_dictionary_of_toolbox_panels()
        self._toolbox_widget = self._create_toolbox_widget()
        self._hide_toolbox_panels()
        self._toolbox_widget.setEnabled(False)
        self._layout.addWidget(self._toolbox_widget)

    @property
    def frame(self):
        return self._frame

    # @property
    # def create_or_load_new_session_panel(self):
    #     return self._create_or_load_new_session_panel

    @property
    def camera_setup_control_panel(self):
        return self._dictionary_of_toolbox_panels[panel_title_strings["cameras"]]

    @property
    def calibrate_capture_volume_panel(self):
        return self._dictionary_of_toolbox_panels[panel_title_strings["calibration"]]

    @property
    def motion_capture_panel(self):
        return self._dictionary_of_toolbox_panels[panel_title_strings["mocap"]]

    @property
    def process_session_data_panel(self):
        return self.motion_capture_panel.process_session_data_panel

    @property
    def visualize_session_data_panel(self):
        return self.motion_capture_panel.visualize_session_data_panel

    @property
    def toolbox_widget(self):
        return self._toolbox_widget

    def show_toolbox_panels(self):
        for panel in self._dictionary_of_toolbox_panels.values():
            panel.show()

    def _create_toolbox_widget(self):
        toolbox_widget = QToolBox()

        for item_name, panel in self._dictionary_of_toolbox_panels.items():
            toolbox_widget.addItem(panel, item_name)
            toolbox_widget.setCurrentWidget(panel)
        return toolbox_widget

    def _create_dictionary_of_toolbox_panels(self):
        dictionary_of_toolbox_panels = {}
        # self._create_or_load_new_session_panel = WelcomeCreateOrLoadNewSessionPanel()
        dictionary_of_toolbox_panels[
            panel_title_strings["cameras"]
        ] = CameraSetupControlPanel()
        dictionary_of_toolbox_panels[
            panel_title_strings["calibration"]
        ] = CalibrateCaptureVolumePanel()
        dictionary_of_toolbox_panels[
            panel_title_strings["mocap"]
        ] = MotionCapturePanel()

        # self._process_session_data_panel = ProcessSessionDataPanel()
        return dictionary_of_toolbox_panels

    def _hide_toolbox_panels(self):
        for panel in self._dictionary_of_toolbox_panels.values():
            panel.hide()

    def _show_toolbox_panels(self):
        for panel in self._dictionary_of_toolbox_panels.values():
            panel.show()

    def enable_toolbox_panels(self):
        self._toolbox_widget.setEnabled(True)
        self._show_toolbox_panels()
