from PyQt6.QtWidgets import QVBoxLayout, QWidget, QPushButton
from pyqtgraph.parametertree import ParameterTree, Parameter

from src.config.webcam_config import WebcamConfig

default_webcam_config = WebcamConfig()

webcam_setup_parameter_group = Parameter.create(
    name="Webcam",
    type="group",
    children=[
        dict(name="Use this camera?", type="bool", value=True),
        dict(name="Apply settings", type="action"),
        dict(name="Exposure", type="int", value=default_webcam_config.exposure),
        dict(
            name="Resolution Width",
            type="int",
            value=default_webcam_config.resolution_width,
        ),
        dict(
            name="Resolution Height",
            type="int",
            value=default_webcam_config.resolution_height,
        ),
    ],
)


class CameraSetup(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.setLayout(layout)

        detect_camera_button = QPushButton("Detect Cameras")
        detect_camera_button.clicked.connect(lambda: print("hello ;D"))
        layout.addWidget(detect_camera_button)
        layout.addWidget(self._create_webcam_parameter_tree())

    def _create_webcam_parameter_tree(self):
        webcam_parameter_group = webcam_setup_parameter_group
        parameter_tree_widget = ParameterTree()
        parameter_tree_widget.setParameters(webcam_parameter_group)
        return parameter_tree_widget
