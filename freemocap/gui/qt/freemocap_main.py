import logging
import signal
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from freemocap.system.paths_and_files_names import (
    get_freemocap_data_folder_path,
)
from freemocap.gui.qt.main_window.freemocap_main_window import FreemocapMainWindow, EXIT_CODE_REBOOT
from freemocap.gui.qt.utilities.get_qt_app import get_qt_app

repo = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo))

logger = logging.getLogger(__name__)


def sigint_handler(*args):
    """Handler for the SIGINT signal."""
    QApplication.quit()


def qt_gui_main():
    logger.info("Starting main...")
    signal.signal(signal.SIGINT, sigint_handler)
    app = get_qt_app()
    timer = QTimer()
    timer.start(500)
    freemocap_main_window = FreemocapMainWindow(freemocap_data_folder_path=get_freemocap_data_folder_path())
    freemocap_main_window.show()
    timer.timeout.connect(freemocap_main_window.update)

    while True:
        error_code = app.exec()
        logger.info(f"`main` exited with error code: {error_code}")
        freemocap_main_window.close()

        if not error_code == EXIT_CODE_REBOOT:
            print(f"Thank you for using freemocap \U0001F480 \U00002764 \U00002728")
            break

        logger.info("`main` exited with the 'reboot' code, so let's reboot!")

    sys.exit()


if __name__ == "__main__":
    qt_gui_main()
