import logging
import signal
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from src.gui.main.app import get_qt_app
from src.gui.main.main_window.main_window import MainWindow

logger = logging.getLogger(__name__)

gui_loop_count = -1


def sigint_handler(*args):
    """Handler for the SIGINT signal."""
    QApplication.quit()


def log_gui_loop():
    global gui_loop_count
    gui_loop_count += 1
    if gui_loop_count % 10 == 0:
        logger.debug("GUI loop {}".format(gui_loop_count))


if __name__ == "__main__":
    logger.info("Starting main...")
    signal.signal(signal.SIGINT, sigint_handler)
    app = get_qt_app()
    timer = QTimer()
    timer.start(500)
    # timer.timeout.connect(log_gui_loop)  # Let the interpreter run each 500 ms.
    timer.timeout.connect(lambda: None)  # Let the interpreter run each 500 ms.
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
