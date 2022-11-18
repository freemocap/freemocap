from PyQt6.QtWidgets import QApplication
from pyqtgraph import mkQApp

APP = None


def get_qt_app() -> QApplication:
    global APP
    if APP is None:
        APP = mkQApp()

    return APP
