from pyqtgraph import mkQApp

APP = None


def get_qt_app():
    global APP
    if APP is None:
        APP = mkQApp()

    return APP
