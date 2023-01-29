import logging
import signal
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from freemocap.configuration.paths_and_files_names import (
    get_freemocap_data_folder_path,
)
from freemocap.qt_gui.main_window.freemocap_main_window import FreemocapMainWindow
from freemocap.qt_gui.utilities.get_qt_app import get_qt_app

repo = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo))

logger = logging.getLogger(__name__)

# reboot GUI method based on this - https://stackoverflow.com/a/56563926/14662833
EXIT_CODE_REBOOT = -123456789


def sigint_handler(*args):
    """Handler for the SIGINT signal."""
    QApplication.quit()


def qt_gui_main():
    logger.info("Starting main...")
    signal.signal(signal.SIGINT, sigint_handler)
    app = get_qt_app()
    timer = QTimer()
    timer.start(500)

    while True:
        qt_gui_main_window = FreemocapMainWindow(freemocap_data_folder_path=get_freemocap_data_folder_path())
        qt_gui_main_window.show()
        error_code = app.exec()
        logger.info(f"`main` exited with error code: {error_code}")
        qt_gui_main_window.close()
        if error_code != EXIT_CODE_REBOOT:
            logger.info(f"Exiting...")
            break
        else:
            logger.info("`main` exited with the 'reboot' code, so let's reboot!")

    sys.exit()


if __name__ == "__main__":
    qt_gui_main()
