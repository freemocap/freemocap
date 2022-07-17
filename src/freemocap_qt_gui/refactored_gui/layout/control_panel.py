import logging
from time import sleep
from typing import Dict

from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QLabel, QPushButton
from pyqtgraph import LayoutWidget
from pyqtgraph.dockarea import Dock
from pyqtgraph.parametertree import Parameter, ParameterTree

from src.cameras.multicam_manager.cv_camera_manager import OpenCVCameraManager
from src.config.webcam_config import WebcamConfig, webcam_config_to_qt_parameter_list
from src.freemocap_qt_gui.refactored_gui.app import get_qt_app
from src.freemocap_qt_gui.refactored_gui.state.app_state import APP_STATE
from src.freemocap_qt_gui.refactored_gui.workers.cam_detection_thread import CamDetectionWorker

detect_camera_text = 'Detect Available Cameras 🔎🎥'

logger = logging.getLogger(__name__)


class ControlPanel(Dock):
    def __init__(self, main_dock_area, name="Setup 🛠️"):
        super().__init__(name)
        # self._main_window_width += 100
        # self._main_window_height = 500
        # self._main_window_widget.resize(self._main_window_width, self._main_window_height)
        main_dock_area.addDock(self, 'bottom')

        self._setup_panel_layout_widget = self._create_basic_layout()

        self._detect_cameras_button = self._setup_detect_camera()
        self._hint_label = self._create_hint_label()
        self._connect_to_cameras_button = self._create_connect_to_cameras_button()
        self._calibrate_cameras_button = self._create_camera_calibrate_button()
        self._launch_camera_windows_button = self._launch_cam_window_button()
        self.pyqtgraph_app = get_qt_app()
        self._available_cameras_data_tree_widget = None

    def _create_basic_layout(self):
        layout_widget = LayoutWidget()
        self.addWidget(layout_widget)
        return layout_widget

    def _launch_cam_window_button(self):
        launch_cam_window_button = QPushButton(
            '(broken)Record freemocap session 🎥 💀'
        )
        launch_cam_window_button.setEnabled(True)
        # launch_cam_window_button.clicked.connect(self._launch_camera_windows)
        launch_cam_window_button.hide()
        self._setup_panel_layout_widget.addWidget(launch_cam_window_button, row=2, col=1)
        return launch_cam_window_button

    def _create_camera_calibrate_button(self):
        cam_button = QPushButton(
            '(wip) Record Camera Calibration Videos 🎥 📐'
        )
        cam_button.setEnabled(True)
        # cam_button.clicked.connect(self._record_calibration_videos)
        cam_button.hide()
        self._setup_panel_layout_widget.addWidget(cam_button, row=1, col=1)
        return cam_button

    def _create_connect_to_cameras_button(self):
        connect_text = 'Connect to cameras 🎥 ✨'
        connect_cam_button = QPushButton(connect_text)
        connect_cam_button.setEnabled(True)
        # connect_cam_button.clicked.connect(self._connect_to_cameras)
        connect_cam_button.hide()
        self._setup_panel_layout_widget.addWidget(connect_cam_button, row=0, col=1)
        return connect_cam_button

    def _create_hint_label(self):
        hint_label = QLabel(
            "HINT - Keep an eye on your `terminal` for helpful `log` statements ;D")
        hint_label.hide()
        self._setup_panel_layout_widget.addWidget(hint_label, row=1, col=0)
        return hint_label

    def _setup_detect_camera(self):
        detect_cam_button = QPushButton(detect_camera_text)
        detect_cam_button.setEnabled(True)
        detect_cam_button.clicked.connect(self._handle_detect_click)
        self._setup_panel_layout_widget.addWidget(detect_cam_button)
        return detect_cam_button

    def _handle_detect_click(self):
        logger.debug("`Detect Available Cameras` button was pressed")
        self._hint_label.show()
        self._detect_cameras_button.setText("Detecting available cameras....")
        # self.pyqtgraph_app.processEvents()
        thread = QThread()
        worker = CamDetectionWorker()
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(thread.deleteLater)
        thread.start()
        while thread.quit:
            sleep(1)
            print("Thread is running....")
        current_session_id = APP_STATE.session_id
        self._opencv_camera_manager = OpenCVCameraManager(current_session_id)
        webcam_configs = self._opencv_camera_manager.get_available_cameras()

        self._detect_cameras_button.setText('Re-Detect Available Cameras 🔎🎥')
        self._hint_label.hide()

        if self._available_cameras_data_tree_widget is None:
            self.camera_setup_parameter_tree_widget = ParameterTree()
            self._setup_panel_layout_widget.addWidget(self.camera_setup_parameter_tree_widget,
                                                      col=0, row=1)

        self._update_webcam_config_parameter_tree(webcam_configs)
        # self._main_window_width *= 1.618
        # self._main_window_widget.resize(int(self._main_window_width),
        #                                 int(self._main_window_height))
        self._connect_to_cameras_button.show()
        # self._calibrate_cameras_button.show()

        # self._launch_camera_windows_button.show()

        # self._use_previous_calibration_checkbox.show()

    def _update_webcam_config_parameter_tree(self, webcams: Dict[str, WebcamConfig]):
        webcam_param_group = []
        for webcam_id, webcam_cfg in webcams.items():
            param_list = webcam_config_to_qt_parameter_list(webcam_cfg)

            webcam_param_group.append(
                Parameter.create(
                    name=f"Webcam: {webcam_id}",
                    type='group',
                    children=param_list)
            )

        available_webcam_parameters_group = Parameter.create(
            name=f"Available Cameras",
            type='group',
            children=webcam_param_group
        )

        self.camera_setup_parameter_tree_widget.setParameters(available_webcam_parameters_group)
