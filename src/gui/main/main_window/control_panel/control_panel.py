from PyQt6.QtWidgets import QFrame, QStackedLayout, QVBoxLayout, QTabWidget

from src.gui.main.main_window.control_panel.stacked_widget_tabs.new_session_tab import (
    NewSessionTab,
)
from src.gui.main.main_window.control_panel.stacked_widget_tabs.welcome_tab import (
    WelcomeTab,
)


class ControlPanel:
    def __init__(self):
        self._frame = QFrame()
        self._frame.setFrameShape(QFrame.Shape.StyledPanel)
        self._layout = QVBoxLayout()

        self._welcome_tab = WelcomeTab()
        self._new_session_tab = NewSessionTab()
        self._tab_widget = self._create_tab_widget()
        self._layout.addWidget(self._tab_widget)
        self._frame.setLayout(self._layout)

    @property
    def frame(self):
        return self._frame

    @property
    def layout(self):
        return self._layout

    def _create_tab_widget(self):
        tab_widget = QTabWidget()
        tab_widget.setTabPosition(QTabWidget.TabPosition.West)
        tab_widget.addTab(self._welcome_tab, "Welcome")
        tab_widget.addTab(self._new_session_tab, "New Session")
        return tab_widget
