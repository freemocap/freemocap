from PyQt6.QtWidgets import QVBoxLayout, QWidget, QPushButton, QComboBox, QLabel
from pyqtgraph.parametertree import ParameterTree, Parameter

from src.config.webcam_config import WebcamConfig
from src.gui.main.app_state.app_state import APP_STATE
from src.gui.main.qt_utils.clear_layout import clear_layout


class CameraSetupControlPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._panel_layout = QVBoxLayout()
        self.setLayout(self._panel_layout)

        self._panel_layout.addWidget(
            QLabel("Click the Update Button in the Viewing panel")
        )

        self._apply_settings_to_cameras_button = QPushButton(
            "Apply settings to cameras",
        )
        self._apply_settings_to_cameras_button.setEnabled(False)

        self._panel_layout.addWidget(self._apply_settings_to_cameras_button)

        self._parameter_tree_layout = QVBoxLayout()
        self._panel_layout.addLayout(self._parameter_tree_layout)

    @property
    def apply_settings_to_cameras_button(self):
        return self._apply_settings_to_cameras_button

    def update_camera_configs(self):
        clear_layout(self._parameter_tree_layout)
        self._parameter_tree_widget = ParameterTree()
        self._parameter_tree_layout.addWidget(self._parameter_tree_widget)

        self._camera_parameter_groups_dict = {}
        for webcam_id, webcam_config in APP_STATE.camera_configs.items():

            self._camera_parameter_groups_dict[
                webcam_id
            ] = self._create_webcam_parameter_tree(webcam_config)

            self._parameter_tree_widget.addParameters(
                self._camera_parameter_groups_dict[webcam_id]
            )

        self._apply_settings_to_cameras_button.setEnabled(True)

        self._panel_layout.addWidget(self._parameter_tree_widget)

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

    def save_settings_to_app_state(self):
        new_selected_cameras_list = []
        new_camera_configs_dict = {}

        for (
            camera_id,
            camera_parameter_group,
        ) in self._camera_parameter_groups_dict.items():
            if camera_parameter_group.param("Use this camera?").value():
                new_selected_cameras_list.append(camera_id)
                new_camera_configs_dict[camera_id] = WebcamConfig(
                    webcam_id=camera_id,
                    exposure=camera_parameter_group.param("Exposure").value(),
                    resolution_width=camera_parameter_group.param(
                        "Resolution Width"
                    ).value(),
                    resolution_height=camera_parameter_group.param(
                        "Resolution Height"
                    ).value(),
                )
        APP_STATE.selected_cameras = new_selected_cameras_list
        APP_STATE.camera_configs = new_camera_configs_dict
