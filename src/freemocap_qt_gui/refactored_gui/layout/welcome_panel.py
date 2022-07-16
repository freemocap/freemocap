import logging

import pyqtgraph as pg
from PyQt6.QtWidgets import QFormLayout, QLabel, QLineEdit, QPushButton, QWidget
from pyqtgraph.dockarea import Dock

from src.config.home_dir import create_session_id
from src.freemocap_qt_gui.refactored_gui.layout.control_panel import ControlPanel
from src.freemocap_qt_gui.refactored_gui.state.app_state import APP_STATE

logger = logging.getLogger(__name__)

start_button_text = 'Start new session'


class WelcomePanel(Dock):
    def __init__(self, main_dock_area, name="init"):
        super().__init__(name)
        self._main_dock_area = main_dock_area
        self.setStretch(1, 1)
        self._welcome_panel_layout_widget = pg.LayoutWidget()
        self.addWidget(self._welcome_panel_layout_widget)
        main_dock_area.addDock(self, size=(1, 1))
        self.create_welcome_label()
        self._session_id_line_edit = self.add_session_id_input()
        self._start_button = self.add_start_button()
        self._shutdown_button = self.add_shutdown_button()

    def create_welcome_label(self):
        welcome_label = QLabel("Welcome to Freemocap 💀✨")
        self._welcome_panel_layout_widget.addWidget(welcome_label, row='next')

    def add_session_id_input(self):
        session_id_layout = QFormLayout()
        session_id_line_edit = QLineEdit(create_session_id())
        session_id_layout.addRow("Session ID: ", session_id_line_edit)
        session_id_widget = QWidget()
        session_id_widget.setLayout(session_id_layout)
        self._welcome_panel_layout_widget.addWidget(session_id_widget, row='next')
        return session_id_line_edit

    def add_start_button(self):
        start_button = QPushButton('Start new session')
        start_button.setEnabled(True)
        start_button.clicked.connect(self._handle_start_click)
        self._welcome_panel_layout_widget.addWidget(start_button, row='next')
        return start_button

    def _handle_start_click(self):
        logger.debug('start button pressed')
        self._start_button.text = start_button_text

        self._shutdown_button.show()

        self._save_session_id(self._session_id_line_edit.text())
        self._start_button.setText("Reset 💫")
        self._start_button.hide()
        self._create_setup_control_panel()

    def add_shutdown_button(self):
        shut_down_button = QPushButton('Shut it down! 🦕')
        shut_down_button.hide()
        shut_down_button.setEnabled(True)
        shut_down_button.clicked.connect(self._handle_shutdown_button)
        self._welcome_panel_layout_widget.addWidget(shut_down_button, row='next')
        return shut_down_button

    def _handle_shutdown_button(self):
        print("shutdown was clicked")

    def _save_session_id(self, session_id: str):
        APP_STATE.session_id = session_id

    def _set_line_edit_to_readonly(self):
        self._session_id_line_edit.setReadOnly(True)
        self._session_id_line_edit.setStyleSheet("QLineEdit"
                                                "{"
                                                "background : lightgrey;"
                                                "}")

    def _create_setup_control_panel(self):
        control_panel = ControlPanel(self._main_dock_area)
