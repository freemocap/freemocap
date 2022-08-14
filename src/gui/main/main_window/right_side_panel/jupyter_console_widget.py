from typing import Dict

import numpy as np
from PyQt6.QtWidgets import QWidget
from qtconsole.manager import QtKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget

from src.gui.main.app import get_qt_app


def make_jupyter_widget_with_kernel():
    """Start a kernel, connect to it, and create a RichJupyterWidget to use it"""
    kernel_manager = QtKernelManager(kernel_name="python3")
    kernel_manager.start_kernel()

    kernel_client = kernel_manager.client()
    kernel_client.start_channels()

    jupyter_widget = RichJupyterWidget()
    jupyter_widget.kernel_manager = kernel_manager
    jupyter_widget.kernel_client = kernel_client
    return jupyter_widget


class PythonConsoleWidget(QWidget):
    def __init__(self, dark_mode: bool = True):
        super().__init__()

        self._jupyter_console_widget = make_jupyter_widget_with_kernel()
        self._import_stuff()

        self.execute("import numpy as np")
        self.execute("%whos", hidden=True)

        get_qt_app().aboutToQuit.connect(self.shutdown_kernel)

        if dark_mode:
            self._jupyter_console_widget.set_default_style("linux")

    @property
    def jupyter_console_widget(self):
        return self._jupyter_console_widget

    def _import_stuff(self):
        self.execute("import matplotlib.pyplot as plt")

    def execute(self, code: str, hidden: bool = False):
        self._jupyter_console_widget.execute(code, hidden=hidden)

    def print(self, message: str):
        self.execute(f"print('{message}')")

    def shutdown_kernel(self):
        self._jupyter_console_widget.kernel_client.stop_channels()
        self._jupyter_console_widget.kernel_manager.shutdown_kernel()
