import logging
import multiprocessing
import threading
from logging.handlers import QueueHandler
from queue import Queue

from PyQt6 import QtCore
from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QApplication, QPlainTextEdit

logger = logging.getLogger(__name__)

log_view_logging_format_string = (
    "[%(asctime)s.%(msecs)04d] [%(levelname)4s] [%(name)s:%(funcName)s():%(lineno)s] :::::: %(message)s"
)

log_view_logging_formatter = logging.Formatter(fmt=log_view_logging_format_string, datefmt="%Y-%m-%dT%H:%M:%S")


class LoggingQueueListener(QThread):
    log_message_signal = QtCore.pyqtSignal(str)

    def __init__(self, logging_queue: Queue, exit_event: threading.Event, parent=None):
        super().__init__(parent)
        self._logging_queue = logging_queue
        self._exit_event = exit_event

    def run(self):
        logger.info("Starting LoggingQueueListener thread")
        try:
            while not self._exit_event.is_set():
                if self._logging_queue.empty():
                    continue

                record = self._logging_queue.get(block=True)

                if record is None:
                    break
                self.log_message_signal.emit(record.message)
        except Exception as e:
            logger.exception(f"Exception in LoggingQueueListener thread: {e}")


class LogViewWidget(QPlainTextEdit):
    # adapted from - https://stackoverflow.com/a/63853259/14662833
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)

        self._logging_queue = multiprocessing.Queue(-1)
        self._queue_handler = QueueHandler(self._logging_queue)
        self._queue_handler.setFormatter(log_view_logging_formatter)
        logging.getLogger("").handlers.append(self._queue_handler)

        self._exit_event = threading.Event()
        self._logging_queue_listener = LoggingQueueListener(
            logging_queue=self._logging_queue, exit_event=self._exit_event
        )
        self._logging_queue_listener.log_message_signal.connect(self.add_log)

        self._logging_queue_listener.start()

    def add_log(self, message):
        self.appendPlainText(message.rstrip())

    def closeEvent(self, event):
        logger.info("Closing LogViewWidget")
        self._exit_event.set()
        self._logging_queue_listener.exit()
        self._logging_queue_listener.wait()
        logging.getLogger("").handlers.remove(self._queue_handler)
        super().closeEvent(event)


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    log_view_widget = LogViewWidget()
    log_view_widget.show()
    sys.exit(app.exec())
