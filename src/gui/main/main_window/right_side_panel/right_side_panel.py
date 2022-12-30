from pathlib import Path
from typing import Union

from PyQt6.QtWidgets import QFrame, QTabWidget, QVBoxLayout

from src.gui.main.main_window.right_side_panel.file_system_view_widget import (
    FileSystemViewWidget,
)
from src.gui.main.main_window.right_side_panel.jupyter_console_widget import (
    JupyterConsoleWidget,
)


class RightSidePanel(QTabWidget):
    def __init__(self, freemocap_data_folder_path: Union[str, Path]):
        super().__init__()
        self._frame = QFrame()
        self._frame.setFrameShape(QFrame.Shape.StyledPanel)
        self._layout = QVBoxLayout()
        self._frame.setLayout(self._layout)

        self._file_viewer_tab_widget = QTabWidget()
        self._layout.addWidget(self._file_viewer_tab_widget)

        self._file_system_view_widget = FileSystemViewWidget(
            freemocap_data_folder_path=freemocap_data_folder_path
        )
        self._file_viewer_tab_widget.addTab(
            self._file_system_view_widget, "Motion Capture Sessions"
        )

        self._log_and_console_tab_widget = QTabWidget()
        self._layout.addWidget(self._log_and_console_tab_widget)

        self._jupyter_console_widget = JupyterConsoleWidget()
        self._log_and_console_tab_widget.addTab(
            self._jupyter_console_widget.jupyter_widget,
            "iPython Jupyter Console",
        )

    @property
    def frame(self):
        return self._frame

    @property
    def file_system_view_widget(self):
        return self._file_system_view_widget

    @property
    def jupyter_console_widget(self):
        return self._jupyter_console_widget

    # def _create_jupyter_console_widget(self):
    #     # create jupyter console widget
    #     jupyter_widget = JupyterConsoleWidget()
    #     # get_qt_app().aboutToQuit.connect(jupyter_widget.shutdown_kernel)
    #
    #     return jupyter_widget

    def _create_log_widget(self):
        pass
