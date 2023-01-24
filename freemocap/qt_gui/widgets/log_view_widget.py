import logging

from PyQt6 import QtCore
from PyQt6.QtWidgets import QApplication, QPlainTextEdit
from PyQt6.uic.properties import QtWidgets

from freemocap.configuration.logging.configure_logging import default_logging_formatter


class LogViewWidget(QPlainTextEdit):
    # adapted from - https://stackoverflow.com/a/63853259/14662833
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self._process = QtCore.QProcess()
        self._process.readyReadStandardOutput.connect(self.handle_stdout)
        self._process.readyReadStandardError.connect(self.handle_stderr)

        widget_handler = logging.StreamHandler(self)
        widget_handler.setLevel(logging.INFO)
        widget_handler.setFormatter(default_logging_formatter)
        logging.getLogger("").handlers.append(widget_handler)

    def start_log(self, program, arguments=None):
        if arguments is None:
            arguments = []
        self._process.start(program, arguments)

    def write(self, message):
        self.add_log(message)

    def add_log(self, message):
        self.appendPlainText(message.rstrip())

    def handle_stdout(self):
        message = self._process.readAllStandardOutput().data().decode()
        self.add_log(message)

    def handle_stderr(self):
        message = self._process.readAllStandardError().data().decode()
        self.add_log(message)


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    log_view_widget = LogViewWidget()
    log_view_widget.start_log(
        "python", ["-c", "import time; print('hello'); time.sleep(1); print('world')"]
    )
    log_view_widget.show()
    sys.exit(app.exec())
