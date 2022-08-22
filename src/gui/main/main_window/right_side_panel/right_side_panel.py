from PyQt6.QtWidgets import QFrame, QVBoxLayout

from src.gui.main.app import get_qt_app
from src.gui.main.main_window.right_side_panel.file_system_view_widget import (
    FileSystemViewWidget,
)
from src.gui.main.main_window.right_side_panel.jupyter_console_widget import (
    PythonConsoleWidget,
)


class RightSidePanel:
    def __init__(self):
        self._frame = QFrame()
        self._frame.setFrameShape(QFrame.Shape.StyledPanel)
        self._layout = QVBoxLayout()
        self._frame.setLayout(self._layout)

        self._file_system_view_widget = FileSystemViewWidget()
        self._layout.addWidget(self._file_system_view_widget)

        # self._python_console_widget = self._create_python_console_widget()
        # self._layout.addWidget(self._python_console_widget.jupyter_console_widget)

    @property
    def frame(self):
        return self._frame

    @property
    def file_system_view_widget(self):
        return self._file_system_view_widget

    @property
    def jupyter_console_widget(self):
        return self._python_console_widget.jupyter_console_widget

    def _create_python_console_widget(self):
        # create jupyter console widget
        python_console_widget = PythonConsoleWidget()
        get_qt_app().aboutToQuit.connect(python_console_widget.shutdown_kernel)

        return python_console_widget
