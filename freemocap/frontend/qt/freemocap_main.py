import logging
import multiprocessing
import signal
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from freemocap.frontend.qt.main_window.freemocap_main_window import FreemocapMainWindow, EXIT_CODE_REBOOT
from freemocap.utilities.fix_opencv_conflict import fix_opencv_conflict

logging.getLogger("matplotlib").setLevel(logging.WARNING)

repo = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo))

logger = logging.getLogger(__name__)


def sigint_handler(*args):
    """Handler for the SIGINT signal."""
    QApplication.quit()


def freemocap_gui_main(global_kill_flag:multiprocessing.Value):
    logger.info("Starting main...")
    signal.signal(signal.SIGINT, sigint_handler)
    app =  QApplication()
    timer = QTimer()
    timer.start(500)



    while not global_kill_flag.value:
        freemocap_main_window = FreemocapMainWindow()
        logger.info("Showing main window - Ready to start!")

        freemocap_main_window.show()

        if freemocap_main_window._user_settings.show_welcome_screen:
            freemocap_main_window.open_welcome_screen_dialog()

        fix_opencv_conflict()

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
    freemocap_gui_main(multiprocessing.Value("b", False))
