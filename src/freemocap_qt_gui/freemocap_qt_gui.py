import logging
from contextlib import contextmanager
from typing import Dict

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtWidgets import QLineEdit, QFormLayout, QWidget, QVBoxLayout, QPushButton
from pyqtgraph.dockarea.DockArea import DockArea
from pyqtgraph.dockarea.Dock import Dock

from pyqtgraph.Qt import QtWidgets
import pyqtgraph as pg
from pyqtgraph.parametertree import ParameterTree, Parameter

from rich import print

from src.api.routes.session.session_router import SessionCalibrateModel, calibrate_session, record_session, \
    SessionIdModel
from src.cameras.detection.cam_singleton import get_or_create_cams
from src.cameras.multicam_manager.cv_camera_manager import OpenCVCameraManager
from src.config.home_dir import create_session_id
from src.config.webcam_config import WebcamConfig, webcam_config_to_qt_parameter_list

logger = logging.getLogger(__name__)

default_webcam_config = WebcamConfig()


class FreemocapQtGUI:
    def __init__(self):
        self.pyqtgraph_app = pg.mkQApp('freemocap! :D')
        self._setup_and_launch()
        self._session_id = None
        self._shut_it_down = False
        self.gui_update_number = -1
        self._dictionary_of_available_webcams = {}
        self._available_cameras_data_tree_widget = None
        self._have_calibration_bool = False

    @property
    def session_id(self):
        return self._session_id

    @property
    def is_running(self):
        return not self._shut_it_down

    def run(self):
        logger.info('launching freemocap GUI')
        self._setup_and_launch()

    def update(self):
        self.gui_update_number += 1
        if self.gui_update_number % 1000:
            print(f"gui update number: {self.gui_update_number})")

    def _setup_and_launch(self):
        self._setup_main_window()
        self._setup_welcome_panel()
        self._main_window_widget.show()

    def _setup_main_window(self, window_width: int = 300, window_height: int = 1):
        """
        This is the main main window for the GUI.
        Its structure is based loosely on the 'Dock Widgets' example from `python -m pyqtgraph.examples`
        """
        self._main_window_width = window_width
        self._main_window_height = window_height

        self._main_window_widget = QtWidgets.QMainWindow()
        self._main_window_widget.resize(self._main_window_width , self._main_window_height)

        self._main_dock_area = DockArea()
        self._main_window_widget.setCentralWidget(self._main_dock_area)
        self._main_window_widget.setWindowTitle('freemocap 💀✨')

    def _setup_welcome_panel(self):
        self._welcome_panel_dock = Dock("freemocap", size=(1, 1))
        self._welcome_panel_layout_widget = pg.LayoutWidget()
        self._welcome_panel_dock.addWidget(self._welcome_panel_layout_widget)
        self._main_dock_area.addDock(self._welcome_panel_dock, size=(1, 1))

        welcome_label = QtWidgets.QLabel("Welcome to Freemocap 💀✨")
        self._welcome_panel_layout_widget.addWidget(welcome_label, row='next')

        session_id_layout = QFormLayout()
        self.session_id_line_edit = QLineEdit(create_session_id())
        session_id_layout.addRow("session_id: ", self.session_id_line_edit)
        session_id_widget = QWidget()
        session_id_widget.setLayout(session_id_layout)
        self._welcome_panel_layout_widget.addWidget(session_id_widget, row='next')

        self._start_button = QtWidgets.QPushButton('Start new session')
        self._start_button.setEnabled(True)
        self._start_button.clicked.connect(self._start)

        self._welcome_panel_layout_widget.addWidget(self._start_button, row='next')

    def _create_setup_control_panel(self):
        self._main_window_widget.resize(self._main_window_width+100, 400)
        self._setup_panel_dock = Dock("Setup 🛠️")
        self._setup_panel_layout_widget = pg.LayoutWidget()
        self._setup_panel_dock.addWidget(self._setup_panel_layout_widget)
        self._main_dock_area.addDock(self._setup_panel_dock,
                                     'bottom',
                                     self._welcome_panel_dock)

        self._detect_cameras_button = QtWidgets.QPushButton('Detect Available Cameras 🔎🎥')
        self._detect_cameras_button.setEnabled(True)
        self._detect_cameras_button.clicked.connect(self._detect_available_cameras)
        self._setup_panel_layout_widget.addWidget(self._detect_cameras_button)

        self.hint_label = QtWidgets.QLabel("HINT - Keep an eye on your `terminal` for helpful `log` statements ;D")
        self.hint_label.hide()
        self._setup_panel_layout_widget.addWidget(self.hint_label, row=1, col=0)

        self._calibrate_cameras_button = QtWidgets.QPushButton('Record Camera Calibration Videos 🎥 📐')
        self._calibrate_cameras_button.setEnabled(True)
        self._calibrate_cameras_button.clicked.connect(self._record_calibration_videos)
        self._calibrate_cameras_button.hide()
        self._setup_panel_layout_widget.addWidget(self._calibrate_cameras_button, row=0, col=1)

        self._use_previous_calibration_checkbox = QtWidgets.QCheckBox("Use Previous Calibration 🎥 ⏳")
        self._use_previous_calibration_checkbox.setChecked(False)
        self._use_previous_calibration_checkbox.stateChanged.connect(self._check_if_have_calibration)
        self._use_previous_calibration_checkbox.hide()
        self._setup_panel_layout_widget.addWidget(self._use_previous_calibration_checkbox, row=1, col=1)

        self._launch_camera_windows_button = QtWidgets.QPushButton('Record freemocap session 🎥 💀')
        self._launch_camera_windows_button.setEnabled(True)
        self._launch_camera_windows_button.clicked.connect(self._launch_camera_windows)
        self._launch_camera_windows_button.hide()
        self._setup_panel_layout_widget.addWidget(self._launch_camera_windows_button, row=2, col=1)

    def _start(self):
        logger.debug('start button pressed')
        self._lock_in_session_id(self.session_id_line_edit.text())
        # self._start_button.setText("Reset 💫")
        self._start_button.hide()
        self._create_setup_control_panel()

    def _check_if_have_calibration(self):
        if self._have_calibration_bool or self._use_previous_calibration_checkbox.isChecked():
            self._launch_camera_windows_button.show()
        else:
            self._launch_camera_windows_button.hide()

    def _launch_camera_windows(self):
        logger.debug("`launch camera windows` button pressed")
        session_id_model = SessionIdModel(session_id=self.session_id)
        # record new session\
        record_session(session_id_model)

    def _record_calibration_videos(self):
        logger.debug("`launch camera windows` button pressed")
        # #calibrate_session
        session_calibrate_model = SessionCalibrateModel(session_id=self._session_id,
                                                        charuco_square_size=39)
        calibrate_session(session_calibrate_model)
        self._have_calibration_bool = True

    def _detect_available_cameras(self):
        logger.debug("`Detect Available Cameras` button was pressed")
        self.hint_label.show()
        self._detect_cameras_button.setText("Detecting available cameras....")
        self.pyqtgraph_app.processEvents()

        self._opencv_camera_manager = OpenCVCameraManager(self.session_id)
        self._dictionary_of_available_webcams = self._opencv_camera_manager.get_available_cameras()

        logger.debug(
            f"`get_or_create_cams()` returned:_available_cameras_dictionary {self._dictionary_of_available_webcams}")
        self._detect_cameras_button.setText('Re-Detect Available Cameras 🔎🎥')
        self.hint_label.hide()

        if self._available_cameras_data_tree_widget is None:
            self.camera_setup_parameter_tree_widget = ParameterTree()
            self._setup_panel_layout_widget.addWidget(self.camera_setup_parameter_tree_widget, col=0, row=1)

        self._update_webcam_config_parameter_tree(self._dictionary_of_available_webcams)
        # self._launch_camera_windows_button.show()
        self._calibrate_cameras_button.show()
        self._use_previous_calibration_checkbox.show()

    def _update_webcam_config_parameter_tree(self,
                                             dictionary_of_available_webcams: Dict[str, WebcamConfig]):
        list_of_webcam_parameters_groups = []
        for this_webcam_id, this_webcam_config in dictionary_of_available_webcams.items():
            this_webcam_parameters_list = webcam_config_to_qt_parameter_list(this_webcam_config)

            list_of_webcam_parameters_groups.append(Parameter.create(name=f"Webcam: {this_webcam_id}", type='group',
                                                                     children=this_webcam_parameters_list))

        available_webcam_parameters_group = Parameter.create(name=f"Available Cameras", type='group',
                                                             children=list_of_webcam_parameters_groups)

        self.camera_setup_parameter_tree_widget.setParameters(available_webcam_parameters_group)

    def _lock_in_session_id(self, session_id: str):
        self._session_id = session_id
        self.session_id_line_edit.setReadOnly(True)
        self.session_id_line_edit.setStyleSheet("QLineEdit"
                                                "{"
                                                "background : lightgrey;"
                                                "}")

    def _reset(self):
        print('i dont know how to reset things lol')


if __name__ == "__main__":
    gui = FreemocapQtGUI()
    pg.exec()
