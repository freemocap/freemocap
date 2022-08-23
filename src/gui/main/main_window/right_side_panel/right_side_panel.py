from PyQt6.QtWidgets import QFrame, QVBoxLayout, QTabWidget

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
        self._main_layout = QVBoxLayout()
        self._frame.setLayout(self._main_layout)

        self._file_viewer_tab_widget = QTabWidget()
        self._main_layout.addWidget(self._file_viewer_tab_widget)

        self._mocap_file_system_view_widget = FileSystemViewWidget()
        self._file_viewer_tab_widget.addTab(
            self._mocap_file_system_view_widget, "Motion Capture Sessions"
        )

        self._log_and_console_tab_widget = QTabWidget()
        self._main_layout.addWidget(self._log_and_console_tab_widget)

        self._python_console_widget = self._create_python_console_widget()
        self._log_and_console_tab_widget.addTab(
            self._python_console_widget.jupyter_console_widget,
            "iPython Jupyter Console",
        )

        self._log_widget = self._create_log_widget()

    @property
    def frame(self):
        return self._frame

    @property
    def file_system_view_widget(self):
        return self._mocap_file_system_view_widget

    @property
    def jupyter_console_widget(self):
        return self._python_console_widget.jupyter_console_widget

    def _create_python_console_widget(self):
        # create jupyter console widget
        python_console_widget = PythonConsoleWidget()
        get_qt_app().aboutToQuit.connect(python_console_widget.shutdown_kernel)

        return python_console_widget

    def _create_log_widget(self):
        pass
