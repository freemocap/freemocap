from PyQt6.QtWidgets import QFrame, QVBoxLayout

from src.gui.main.app import get_qt_app
from src.gui.main.main_window.jupyter_console_panel.jupyter_console_widget import (
    JupyterConsoleWidget,
)


class JupyterConsolePanel:
    def __init__(self):
        self._frame = QFrame()
        self._frame.setFrameShape(QFrame.Shape.StyledPanel)
        self._layout = QVBoxLayout()
        self._frame.setLayout(self._layout)

        self._jupyter_console_widget = self._create_jupyter_console_widget()
        self._layout.addWidget(self._jupyter_console_widget)

    def _create_jupyter_console_widget(self):
        # create jupyter console widget
        jupyter_console_widget = JupyterConsoleWidget()
        get_qt_app().aboutToQuit.connect(jupyter_console_widget.shutdown_kernel)

        return jupyter_console_widget

    @property
    def frame(self):
        return self._frame

    @property
    def layout(self):
        return self._layout
