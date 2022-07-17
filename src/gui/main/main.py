import signal
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

# from src.api.routes.session.session_router import visualize_session_offline
from src.gui.main.app import get_qt_app
from src.gui.main.layout.main_window import MainWindow


def sigint_handler(*args):
    """Handler for the SIGINT signal."""
    QApplication.quit()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, sigint_handler)
    app = get_qt_app()
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)  # Let the interpreter run each 500 ms.
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
    # app.exec()
    # visualize_session_offline()
