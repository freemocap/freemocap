from PyQt6.QtWidgets import QFrame, QStackedLayout, QVBoxLayout, QTabWidget, QLabel

from src.gui.main.main_window.control_panel.stacked_widget_tabs.new_session_tab import (
    NewSessionTab,
)
from src.gui.main.main_window.control_panel.stacked_widget_tabs.welcome_tab import (
    SelectWorkflowScreen,
)
from src.gui.main.qt_utils.clear_layout import clearLayout


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

    def _start_standard_workflow(self):
        clearLayout(self._layout)
        self._create_tab_widget()

    def _create_tab_widget(self):
        tab_widget = QTabWidget()
        tab_widget.setTabPosition(QTabWidget.TabPosition.West)
        tab_widget.addTab(QLabel("Camera Setup"), "Camera Setup")
        tab_widget.addTab(
            QLabel("Calibrate Capture Volume"), "Calibrate Capture Volume"
        )
        tab_widget.addTab(
            QLabel("Record FreeMoCap Session"), "Record FreeMoCap Session"
        )
        tab_widget.addTab(
            QLabel("View Motion Capture Data"), "View Motion Capture Data"
        )

        self._layout.addWidget(tab_widget)
