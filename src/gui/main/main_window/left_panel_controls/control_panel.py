from PyQt6.QtWidgets import (
    QFrame,
    QStackedLayout,
    QVBoxLayout,
    QTabWidget,
    QLabel,
    QToolBox,
)
from pyqtgraph.parametertree import ParameterTree, Parameter

from src.cameras.detection.cam_singleton import get_or_create_cams
from src.config.webcam_config import WebcamConfig
from src.gui.icis_conference_main.state.app_state import APP_STATE
from src.gui.main.main_window.left_panel_controls.toolbox_widgets.camera_setup_control_panel import (
    CameraSetupControlPanel,
)
from src.gui.main.main_window.left_panel_controls.toolbox_widgets.new_session_tab import (
    NewSessionTab,
)
from src.gui.main.main_window.left_panel_controls.toolbox_widgets.welcome_tab import (
    SelectWorkflowScreen,
)
from src.gui.main.qt_utils.clear_layout import clear_layout


class ControlPanel:
    def __init__(self):
        self._frame = QFrame()
        self._frame.setFrameShape(QFrame.Shape.StyledPanel)
        self._layout = QVBoxLayout()

        self._select_workflow_screen = SelectWorkflowScreen()
        self._select_workflow_screen.start_new_session_button.clicked.connect(
            self._start_standard_workflow
        )
        self._layout.addWidget(self._select_workflow_screen)
        self._frame.setLayout(self._layout)

    @property
    def frame(self):
        return self._frame

    @property
    def layout(self):
        return self._layout

    @property
    def select_workflow_screen(self):
        return self._select_workflow_screen

    def _start_standard_workflow(self):
        clear_layout(self._layout)
        self._create_toolbox_widget()

    def _create_toolbox_widget(self):
        toolbox_widget = QToolBox()
        toolbox_widget.addItem(CameraSetupControlPanel(), "Camera Setup")
        toolbox_widget.setItemToolTip(0, "This is a tooltip for Camera Setup")

        toolbox_widget.addItem(
            QLabel("Calibrate Capture Volume"), "Calibrate Capture Volume"
        )

        toolbox_widget.addItem(
            QLabel("Record FreeMoCap Session"), "Record Synchronized Videos"
        )
        toolbox_widget.addItem(QLabel("Process Data"), "Process Data")
        toolbox_widget.addItem(
            QLabel("View Motion Capture Data"), "View Motion Capture Data"
        )

        self._layout.addWidget(toolbox_widget)
