import logging

from PyQt6.QtCore import pyqtSignal, QThread

logger = logging.getLogger(__name__)


class MinimalExampleThreadWorker(QThread):
    finished = pyqtSignal(str)

    def run(self):
        self.finished.emit("Done!")
