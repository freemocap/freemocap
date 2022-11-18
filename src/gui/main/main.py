import logging
import signal
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from pathlib import Path

repo = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo))


from src.gui.main.style_stuff.css_style_sheet import qt_app_css_style_sheet

from src.gui.main.app import get_qt_app
from src.gui.main.main_window.main_window import MainWindow, EXIT_CODE_REBOOT

logger = logging.getLogger(__name__)

loop_count = -1


def sigint_handler(*args):
    """Handler for the SIGINT signal."""
    QApplication.quit()


if __name__ == "__main__":
    logger.info("Starting main...")
    signal.signal(signal.SIGINT, sigint_handler)
    app = get_qt_app()
    app.setStyleSheet(qt_app_css_style_sheet)
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(
        lambda: None
    )  # Let the interpreter calculate_center_of_mass each 500 ms.

    while True:
        # rebootable GUI method based on this - https://stackoverflow.com/a/56563926/14662833
        win = MainWindow()
        win.show()
        error_code = app.exec()
        logger.info(f"`main` exited with error code: {error_code}")
        win.close()
        if error_code != EXIT_CODE_REBOOT:
            logger.info(f"Exiting...")
            break
        else:
            logger.info("`main` exited with the 'reboot' code, so let's reboot!")

    sys.exit()
