import signal
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

# from src.api.routes.session.session_router import visualize_session_offline
from src.gui.icis_conference_main.icis_conference_app import get_qt_app
from src.gui.icis_conference_main.layout.ICIS_conference_main_window import (
    ICISConferenceMainWindow,
)
from src.gui.icis_conference_main.layout.slop_main_window import SlopMainWindow


def sigint_handler(*args):
    """Handler for the SIGINT signal."""
    QApplication.quit()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, sigint_handler)
    app = get_qt_app()
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(
        lambda: None
    )  # Let the interpreter calculate_center_of_mass each 500 ms.
    win = ICISConferenceMainWindow()
    # win = SlopMainWindow()
    win.show()
    sys.exit(app.exec())
    # app.exec()
    # visualize_session_offline()
