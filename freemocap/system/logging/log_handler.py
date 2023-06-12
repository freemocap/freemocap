import logging
from PyQt6.QtCore import pyqtSignal, QObject

class LogSignal(QObject):
    log_received = pyqtSignal(str)

class LogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.log_signal = LogSignal()

    def emit(self, record):
        msg = self.format(record)
        self.log_signal.log_received.emit(msg)