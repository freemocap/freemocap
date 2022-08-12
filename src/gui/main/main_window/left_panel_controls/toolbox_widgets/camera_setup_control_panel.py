from PyQt6.QtWidgets import QVBoxLayout, QWidget, QPushButton, QComboBox
from pyqtgraph.parametertree import ParameterTree, Parameter

from src.config.webcam_config import WebcamConfig
from src.gui.main.app_state.app_state import APP_STATE
from src.gui.main.qt_utils.clear_layout import clear_layout


class CameraSetupControlPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        detect_cameras_button = QPushButton("Detect Cameras")
        detect_cameras_button.clicked.connect(lambda: print("hello ;D"))
        self._layout.addWidget(detect_cameras_button)

    def update_camera_configs(self):
        parameter_tree_widget = ParameterTree()

        for webcam_id, webcam_config in APP_STATE.camera_configs.items():
            camera_parameter_group = self._create_webcam_parameter_tree(webcam_config)
            parameter_tree_widget.addParameters(camera_parameter_group)

        clear_layout(self._layout)
        self._layout.addWidget(parameter_tree_widget)

    def _create_webcam_parameter_tree(self, webcam_config: WebcamConfig):
        return Parameter.create(
            name="Camera_" + str(webcam_config.webcam_id),
            type="group",
            children=[
                dict(name="Use this camera?", type="bool", value=True),
                dict(name="Apply settings", type="action"),
                dict(name="Exposure", type="int", value=webcam_config.exposure),
                dict(
                    name="Resolution Width",
                    type="int",
                    value=webcam_config.resolution_width,
                ),
                dict(
                    name="Resolution Height",
                    type="int",
                    value=webcam_config.resolution_height,
                ),
            ],
        )
