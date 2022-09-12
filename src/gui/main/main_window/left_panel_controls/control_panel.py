from typing import List

from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QLabel,
    QToolBox,
)

from src.cameras.detection.models import FoundCamerasResponse
from src.config.webcam_config import WebcamConfig
from src.gui.main.main_window.left_panel_controls.toolbox_widgets.calibrate_capture_volume_panel import (
    CalibrateCaptureVolumePanel,
)
from src.gui.main.main_window.left_panel_controls.toolbox_widgets.camera_setup_control_panel import (
    CameraSetupControlPanel,
)
from src.gui.main.main_window.left_panel_controls.toolbox_widgets.welcome_create_or_load_new_session_panel import (
    WelcomeCreateOrLoadNewSessionPanel,
)
from src.gui.main.main_window.left_panel_controls.toolbox_widgets.process_session_data_panel import (
    ProcessSessionDataPanel,
)
from src.gui.main.main_window.left_panel_controls.toolbox_widgets.record_motion_capture_videos_panel import (
    RecordMotionCatpureVideosPanel,
)
from src.gui.main.main_window.left_panel_controls.toolbox_widgets.visualize_motion_capture_data import (
    VisualizeMotionCaptureDataPanel,
)

from src.gui.main.qt_utils.clear_layout import clear_layout

import logging

logger = logging.getLogger(__name__)


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
        return self._dictionary_of_toolbox_panels["Camera Setup and Control"]

    @property
    def calibrate_capture_volume_panel(self):
        return self._dictionary_of_toolbox_panels["Calibrate Capture Volume"]

    @property
    def record_motion_capture_videos_panel(self):
        return self._dictionary_of_toolbox_panels[
            "Record and Process Motion Capture Videos"
        ]

    @property
    def process_session_data_panel(self):
        return self.record_motion_capture_videos_panel.process_session_data_panel

    @property
    def visualize_motion_capture_data_panel(self):
        return self._dictionary_of_toolbox_panels["Visualize Motion Capture Data"]

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
            "Camera Setup and Control"
        ] = CameraSetupControlPanel()
        dictionary_of_toolbox_panels[
            "Calibrate Capture Volume"
        ] = CalibrateCaptureVolumePanel()
        dictionary_of_toolbox_panels[
            "Record and Process Motion Capture Videos"
        ] = RecordMotionCatpureVideosPanel()
        dictionary_of_toolbox_panels[
            "Visualize Motion Capture Data"
        ] = VisualizeMotionCaptureDataPanel()
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
