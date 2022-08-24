from typing import List, Dict

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QWidget, QPushButton
from pyqtgraph.parametertree import ParameterTree, Parameter

from src.cameras.detection.models import FoundCamerasResponse
from src.config.webcam_config import WebcamConfig
from src.gui.main.qt_utils.clear_layout import clear_layout

import logging

from src.gui.main.styled_widgets.primary_button import PrimaryButton

logger = logging.getLogger(__name__)


class CameraSetupControlPanel(QWidget):
    camera_parameters_updated_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._panel_layout = QVBoxLayout()
        self.setLayout(self._panel_layout)

        self._redetect_cameras_button = QPushButton("TO DO- Re-Detect Cameras")
        self._redetect_cameras_button.setEnabled(False)
        self._panel_layout.addWidget(self._redetect_cameras_button)

        self._apply_settings_to_cameras_button = PrimaryButton(
            "Apply settings to cameras",
        )
        self._apply_settings_to_cameras_button.setEnabled(True)
        self._panel_layout.addWidget(self._apply_settings_to_cameras_button)

        self._parameter_tree_layout = QVBoxLayout()
        self._parameter_tree_widget = ParameterTree()
        self._parameter_tree_layout.addWidget(self._parameter_tree_widget)
        self._panel_layout.addLayout(self._parameter_tree_layout)

    @property
    def apply_settings_to_cameras_button(self):
        return self._apply_settings_to_cameras_button

    @property
    def redetect_cameras_button(self):
        return self._redetect_cameras_button

    def handle_found_cameras_response(
        self, found_cameras_response: FoundCamerasResponse
    ):
        self._list_of_available_camera_ids = [
            raw_cam.webcam_id for raw_cam in found_cameras_response.cameras_found_list
        ]

        logger.info(f"Found cameras with IDs:  {self._list_of_available_camera_ids}")

        self._dictionary_of_webcam_configs = {}
        for camera_id in self._list_of_available_camera_ids:
            self._dictionary_of_webcam_configs[camera_id] = WebcamConfig(
                webcam_id=camera_id
            )

        self.update_camera_config_parameter_tree()

    def update_camera_config_parameter_tree(self):
        logger.info("Updating camera configs")
        clear_layout(self._parameter_tree_layout)
        self._parameter_tree_widget = ParameterTree()
        self._parameter_tree_layout.addWidget(self._parameter_tree_widget)

        self._camera_parameter_groups_dictionary = {}
        for webcam_id in self._list_of_available_camera_ids:
            if not webcam_id in self._dictionary_of_webcam_configs:

                self._camera_parameter_groups_dictionary[
                    webcam_id
                ] = self._create_webcam_parameter_tree_for_unselected_camera(webcam_id)
            else:
                self._camera_parameter_groups_dictionary[
                    webcam_id
                ] = self._create_webcam_parameter_tree(
                    self._dictionary_of_webcam_configs[webcam_id]
                )

            self._parameter_tree_widget.addParameters(
                self._camera_parameter_groups_dictionary[webcam_id]
            )

        self.camera_parameters_updated_signal.emit(self._dictionary_of_webcam_configs)

    def get_webcam_configs_from_parameter_tree(self):
        new_selected_cameras_list = []
        new_camera_configs_dict = {}

        for (
            camera_id,
            camera_parameter_group,
        ) in self._camera_parameter_groups_dictionary.items():
            if camera_parameter_group.param("Use this camera?").value():
                new_selected_cameras_list.append(camera_id)
                try:
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
                except:
                    new_camera_configs_dict[camera_id] = WebcamConfig(
                        webcam_id=camera_id
                    )
        self._dictionary_of_webcam_configs = new_camera_configs_dict
        self.update_camera_config_parameter_tree()

    def _create_webcam_parameter_tree(self, webcam_config: WebcamConfig):
        return Parameter.create(
            name="Camera_" + str(webcam_config.webcam_id),
            type="group",
            children=[
                dict(name="Use this camera?", type="bool", value=True),
                # dict(name="Apply settings", type="action"),
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

    def _create_webcam_parameter_tree_for_unselected_camera(self, webcam_id):
        return Parameter.create(
            name="Camera_" + str(webcam_id),
            type="group",
            children=[
                dict(name="Use this camera?", type="bool", value=False),
            ],
        )
