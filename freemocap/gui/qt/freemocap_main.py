import logging
import signal
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from freemocap.gui.qt.main_window.freemocap_main_window import MainWindow, EXIT_CODE_REBOOT

logging.getLogger("matplotlib").setLevel(logging.WARNING)

from freemocap.gui.qt.utilities.get_qt_app import get_qt_app
from freemocap.system.paths_and_filenames.path_getters import get_freemocap_data_folder_path
from freemocap.system.user_data.pipedream_pings import PipedreamPings

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

    pipedream_pings = PipedreamPings()

    while True:
        freemocap_main_window = MainWindow(
            freemocap_data_folder_path=get_freemocap_data_folder_path(), pipedream_pings=pipedream_pings
        )
        logger.info("Showing main window - Ready to start!")
        logger.info("Welcome to FreeMoCap 💀✨")
        freemocap_main_window.show()
        if freemocap_main_window._gui_state.show_welcome_screen:
            freemocap_main_window.open_welcome_screen_dialog()
        timer.timeout.connect(freemocap_main_window.update)
        error_code = app.exec()
        logger.info(f"`main` exited with error code: {error_code}")
        freemocap_main_window.close()

        if not error_code == EXIT_CODE_REBOOT:
            print("Thank you for using freemocap \U0001F480 \U00002764 \U00002728")
            break

        logger.info("`main` exited with the 'reboot' code, so let's reboot!")

    sys.exit()


if __name__ == "__main__":
    qt_gui_main()
