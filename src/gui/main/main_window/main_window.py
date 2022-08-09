from PyQt6.QtWidgets import QMainWindow, QHBoxLayout, QWidget

from src.gui.main.main_window.control_panel.control_panel import ControlPanel
from src.gui.main.main_window.jupyter_console_panel.jupyter_console_panel import (
    JupyterConsolePanel,
)
from src.gui.main.main_window.viewing_panel.viewing_panel import ViewingPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("freemocap")
        self._main_window_width = int(1920 * 0.8)
        self._main_window_height = int(1080 * 0.8)
        self.setGeometry(0, 0, self._main_window_width, self._main_window_height)
        self._main_layout = self._create_main_layout()

        # control panel
        self._control_panel = self._create_control_panel()
        self._main_layout.addWidget(self._control_panel.frame)

        # viewing panel
        self._viewing_panel = self._create_viewing_panel()
        self._main_layout.addWidget(self._viewing_panel.frame)

        # jupyter console panel
        self._jupyter_console_widget = self._create_jupyter_console_widget()
        self._main_layout.addWidget(self._jupyter_console_widget.frame)

    def _create_main_layout(self):
        main_layout = QHBoxLayout()
        widget = QWidget()
        widget.setLayout(main_layout)
        self.setCentralWidget(widget)
        return main_layout

    def _create_control_panel(self):
        panel = ControlPanel()
        panel.frame.setFixedWidth(self._main_window_width * 0.2)
        panel.frame.setFixedHeight(self._main_window_height)
        return panel

    def _create_viewing_panel(self):
        panel = ViewingPanel()
        panel.frame.setFixedWidth(self._main_window_width * 0.5)
        panel.frame.setFixedHeight(self._main_window_height)
        return panel

    def _create_jupyter_console_widget(self):
        panel = JupyterConsolePanel()
        panel.frame.setFixedWidth(self._main_window_width * 0.3)
        panel.frame.setFixedHeight(self._main_window_height)
        return panel
