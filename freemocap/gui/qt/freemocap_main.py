import logging
import signal
import sys
from pathlib import Path
from importlib.metadata import distributions

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from freemocap.gui.qt.main_window.freemocap_main_window import MainWindow, EXIT_CODE_REBOOT
from freemocap.gui.qt.utilities.save_and_load_gui_state import GuiState, load_gui_state
from freemocap.system.paths_and_filenames.path_getters import get_gui_state_json_path
from freemocap.system.logging.configure_logging import configure_logging, LogLevel
from freemocap import __package_name__, __version__

logging.getLogger("matplotlib").setLevel(logging.WARNING)

from freemocap.gui.qt.utilities.get_qt_app import get_qt_app
from freemocap.system.user_data.pipedream_pings import PipedreamPings

repo = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo))

logger = logging.getLogger(__name__)


def sigint_handler(*args):
    """Handler for the SIGINT signal."""
    QApplication.quit()


def qt_gui_main():
    print("Starting main...")
    signal.signal(signal.SIGINT, sigint_handler)
    app = get_qt_app()
    timer = QTimer()
    timer.start(500)

    try:
        gui_state = load_gui_state(get_gui_state_json_path())
        print("Successfully loaded previous settings")
    except Exception:
        print("Failed to find previous GUI settings, using default settings")
        gui_state = GuiState()


    configure_logging(LogLevel.TRACE)

    logger = logging.getLogger(__name__)
    logger.info(f"Initializing {__package_name__} package, version: {__version__}, from file: {__file__}")

    pipedream_pings = PipedreamPings()

    while True:
        freemocap_main_window = MainWindow(gui_state=gui_state, pipedream_pings=pipedream_pings)
        logger.info("Showing main window - Ready to start!")

        freemocap_main_window.show()

        if freemocap_main_window._gui_state.show_welcome_screen:
            freemocap_main_window.open_welcome_screen_dialog()
        installed_packages = {dist.metadata["Name"] for dist in distributions()}
        if "opencv-python" in installed_packages and "opencv-contrib-python" in installed_packages:
            freemocap_main_window.open_opencv_conflict_dialog()

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
