import logging

from PyQt6.QtWidgets import QVBoxLayout, QWidget
from qtconsole.manager import QtKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget

logger = logging.getLogger(__name__)


class JupyterConsoleWidget(QWidget):
    def __init__(self, dark_mode: bool = True, parent=None):
        super().__init__(parent=parent)

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._kernel_manager = QtKernelManager(kernel_name="python3")
        self._kernel_manager.start_kernel()

        self._kernel_client = self._kernel_manager.client()
        self._kernel_client.start_channels()

        self._jupyter_widget = RichJupyterWidget()
        self._jupyter_widget.kernel_manager = self._kernel_manager
        self._jupyter_widget.kernel_client = self._kernel_client

        self._layout.addWidget(self._jupyter_widget)

        self._import_stuff()

        self._connect_to_logging()

        # get_qt_app().aboutToQuit.connect(self.shutdown_kernel)

        if dark_mode:
            self._jupyter_widget.set_default_style("linux")

    @property
    def jupyter_widget(self):
        return self._jupyter_widget

    def _start_kernel_and_whatnot(self):
        """Start a kernel, connect to it, and create a RichJupyterWidget to use it"""
        kernel_manager = QtKernelManager(kernel_name="python3")
        kernel_manager.start_kernel()

        kernel_client = kernel_manager.client()
        kernel_client.start_channels()

        jupyter_widget = RichJupyterWidget()
        jupyter_widget.kernel_manager = kernel_manager
        jupyter_widget.kernel_client = kernel_client
        return jupyter_widget

    def _import_stuff(self):
        self.execute("import matplotlib.pyplot as plt", hidden=True)
        self.execute("import numpy as np", hidden=True)
        self.execute("%whos")

    def execute(self, code: str, hidden: bool = False):
        self._jupyter_widget.execute(code, hidden=hidden)

    def print_to_console(self, message: str):
        self.execute(f"print('{message}')")

    def write(self, text: str):
        self._jupyter_widget._append_plain_text(text)

    def shutdown_kernel(self):
        self._jupyter_widget.kernel_client.stop_channels()
        self._jupyter_widget.kernel_manager.shutdown_kernel()

    def _connect_to_logging(self):
        return
        # logger.info("Connecting Jupyter Console Widget to Logging")
        # logging.getLogger("").handlers.append(logging.StreamHandler(self))


if __name__ == "__main__":
    from freemocap.system.logging.configure_logging import configure_logging

    configure_logging()
    logger.info("Hello world!")

    from PyQt6.QtWidgets import QApplication

    app = QApplication([])

    jupyter_widget = JupyterConsoleWidget()
    jupyter_widget.show()

    h = logging.StreamHandler(jupyter_widget)
    logging.getLogger("").handlers.append(h)
    logger.info("Hello world worldddd!")
    logger.info("Hello world worlddd WWWWWEEEEEEE!")

    logger.info("gfsdgdfg!")
    logger.info("gfsdgdfsdfsdfsg!")
    app.exec()
