from PyQt6.QtWidgets import QMainWindow
from pyqtgraph.dockarea import DockArea

from src.freemocap_qt_gui.refactored_gui.layout.welcome_panel import WelcomePanel


class MainWindow(QMainWindow):
    def __init__(self, window_width: int = 300, window_height: int = 1):
        """
        This is the main window for the GUI.
        Its structure is based loosely on the 'Dock Widgets' example from `python -m
        pyqtgraph.examples`
        """
        super().__init__()
        self.resize(window_width, window_height)
        self.setWindowTitle('freemocap 💀✨')

        main_dock_area = DockArea()
        self.setCentralWidget(main_dock_area)

        # Adding components to the window
        self._panel = WelcomePanel(main_dock_area)

