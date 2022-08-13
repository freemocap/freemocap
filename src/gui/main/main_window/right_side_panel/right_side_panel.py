from PyQt6.QtWidgets import QFrame, QVBoxLayout

from src.gui.main.app import get_qt_app
from src.gui.main.main_window.right_side_panel.file_system_view_widget import (
    FileSystemViewWidget,
)
from src.gui.main.main_window.right_side_panel.jupyter_console_widget import (
    JupyterConsoleWidget,
)


class RightSidePanel:
    def __init__(self):
        self._frame = QFrame()
        self._frame.setFrameShape(QFrame.Shape.StyledPanel)
        self._layout = QVBoxLayout()
        self._frame.setLayout(self._layout)

        self._file_system_view_widget = FileSystemViewWidget()
        self._layout.addWidget(self._file_system_view_widget)

        self._jupyter_console_widget = self._create_jupyter_console_widget()
        self._layout.addWidget(self._jupyter_console_widget)

    @property
    def frame(self):
        return self._frame

    @property
    def file_system_view_widget(self):
        return self._file_system_view_widget

    def _create_jupyter_console_widget(self):
        # create jupyter console widget
        jupyter_console_widget = JupyterConsoleWidget()
        get_qt_app().aboutToQuit.connect(jupyter_console_widget.shutdown_kernel)

        return jupyter_console_widget
