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
from src.gui.main.main_window.left_panel_controls.toolbox_widgets.create_or_load_new_session_panel import (
    CreateOrLoadNewSessionPanel,
)
from src.gui.main.main_window.left_panel_controls.toolbox_widgets.process_session_data_panel import (
    ProcessSessionDataPanel,
)
from src.gui.main.main_window.left_panel_controls.toolbox_widgets.record_synchronized_videos_panel import (
    RecordSynchronizedVideosPanel,
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

        self._create_toolbox_panels()
        self._toolbox_widget = self._create_toolbox_widget()
        self._layout.addWidget(self._toolbox_widget)

    @property
    def frame(self):
        return self._frame

    @property
    def camera_setup_control_panel(self):
        return self._camera_setup_control_panel

    @property
    def calibrate_capture_volume_panel(self):
        return self._calibrate_capture_volume_panel

    @property
    def record_synchronized_videos_panel(self):
        return self._record_synchronized_videos_panel

    @property
    def process_session_data_panel(self):
        return self._process_session_data_panel

    @property
    def toolbox_widget(self):
        return self._toolbox_widget

    def _start_standard_workflow(self):
        clear_layout(self._layout)
        self._create_toolbox_widget()

    def _create_toolbox_widget(self):
        toolbox_widget = QToolBox()

        toolbox_widget.addItem(
            self._create_or_load_new_session_panel, "Create or Load Session"
        )

        toolbox_widget.addItem(self._camera_setup_control_panel, "Camera Setup")

        toolbox_widget.addItem(
            self._calibrate_capture_volume_panel, "Calibrate Capture Volume"
        )

        toolbox_widget.addItem(
            self._record_synchronized_videos_panel, "Record Synchronized Videos"
        )
        toolbox_widget.addItem(self._process_session_data_panel, "Process Session Data")

        toolbox_widget.addItem(
            QLabel("View Motion Capture Data"), "View Motion Capture Data"
        )

        return toolbox_widget

    def _create_toolbox_panels(self):
        self._create_or_load_new_session_panel = CreateOrLoadNewSessionPanel()
        self._camera_setup_control_panel = CameraSetupControlPanel()
        self._calibrate_capture_volume_panel = CalibrateCaptureVolumePanel()
        self._record_synchronized_videos_panel = RecordSynchronizedVideosPanel()
        self._process_session_data_panel = ProcessSessionDataPanel()
