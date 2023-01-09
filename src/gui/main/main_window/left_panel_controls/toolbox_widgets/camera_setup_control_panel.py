import logging
from typing import Dict

import cv2
from old_src.cameras.detection.models import FoundCamerasResponse
from old_src.cameras.webcam_config import WebcamConfig
from old_src.gui.main.qt_utils.clear_layout import clear_layout
from old_src.gui.workflow_helper_blurbs.camera_setup_control_panel_help_blurb import (
    camera_setup_control_panel_help_blurb_str,
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from pyqtgraph.parametertree import Parameter, ParameterTree

logger = logging.getLogger(__name__)


def rotate_image_str_to_cv2_code(rotate_str: str):

    if rotate_str == "90_clockwise":
        return cv2.ROTATE_90_CLOCKWISE
    elif rotate_str == "90_counterclockwise":
        return cv2.ROTATE_90_COUNTERCLOCKWISE
    elif rotate_str == "180":
        return cv2.ROTATE_180

    return None


def rotate_cv2_code_to_str(rotate_video_value):
    if rotate_video_value is None:
        return None
    elif rotate_video_value == cv2.ROTATE_90_CLOCKWISE:
        return "90_clockwise"
    elif rotate_video_value == cv2.ROTATE_90_COUNTERCLOCKWISE:
        return "90_counterclockwise"
    elif rotate_video_value == cv2.ROTATE_180:
        return "180"


class CameraSetupControlPanel(QWidget):

    camera_parameters_updated_signal = pyqtSignal(dict)
    new_webcam_configs_received_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        helper_qlabel_widget = QLabel(camera_setup_control_panel_help_blurb_str)
        helper_qlabel_widget.setWordWrap(True)
        self._layout.addWidget(helper_qlabel_widget)

        camera_warning_label = QLabel(
            "NOTE -\nThe current version of the GUI is inefficient and will start dropping frames with ~3+ cameras. This will be fixed in a future version.\n\n"
            "In the meantime, to use more cameras, record them with the `pre-alpha` version of FreeMoCap and import the `[freemocap_data]/[session_id]/SyncedVideos` folder files into the GUI with the `Import Videos` functionality."
        )
        camera_warning_label.setWordWrap(True)
        camera_warning_label.setStyleSheet("color: #770000")
        self._layout.addWidget(camera_warning_label)
        self._layout.addWidget(QLabel())

        self._redetect_cameras_button = QPushButton("Detect Cameras")
        self._redetect_cameras_button.setEnabled(True)
        self._layout.addWidget(self._redetect_cameras_button)

        self._apply_settings_to_cameras_button = QPushButton(
            "Apply settings and Launch Cameras",
        )
        self._apply_settings_to_cameras_button.setEnabled(True)
        self._layout.addWidget(self._apply_settings_to_cameras_button)

        self._pop_dock_buttons_layout = QHBoxLayout()
        self._layout.addLayout(self._pop_dock_buttons_layout)

        self._pop_out_cameras_button = QPushButton("Pop out cameras")
        self._pop_out_cameras_button.setEnabled(True)
        self._pop_dock_buttons_layout.addWidget(self._pop_out_cameras_button)

        self._dock_cameras_button = QPushButton("Dock cameras")
        self._dock_cameras_button.setEnabled(False)
        self._pop_dock_buttons_layout.addWidget(self._dock_cameras_button)

        self._close_cameras_button = QPushButton("Close cameras")
        self._close_cameras_button.setEnabled(True)
        self._layout.addWidget(self._close_cameras_button)

        self._parameter_tree_layout = QVBoxLayout()
        self._parameter_tree_widget = ParameterTree()
        self._parameter_tree_layout.addWidget(self._parameter_tree_widget)
        self._layout.addLayout(self._parameter_tree_layout)

    @property
    def apply_settings_to_cameras_button(self):
        return self._apply_settings_to_cameras_button

    @property
    def redetect_cameras_button(self):
        return self._redetect_cameras_button

    @property
    def pop_out_cameras_button(self):
        return self._pop_out_cameras_button

    @property
    def dock_cameras_button(self):
        return self._dock_cameras_button

    @property
    def close_cameras_button(self):
        return self._close_cameras_button

    def handle_found_cameras_response(
        self, found_cameras_response: FoundCamerasResponse
    ):
        self._list_of_available_camera_ids = found_cameras_response.cameras_found_list

        logger.info(f"Found cameras with IDs:  {self._list_of_available_camera_ids}")

        dictionary_of_webcam_configs = {}
        for camera_id in self._list_of_available_camera_ids:
            dictionary_of_webcam_configs[camera_id] = WebcamConfig(webcam_id=camera_id)

        self._update_camera_config_parameter_tree(dictionary_of_webcam_configs)

    def _update_camera_config_parameter_tree(
        self, dictionary_of_webcam_configs: Dict[str, WebcamConfig]
    ):
        logger.info("Updating camera configs")
        clear_layout(self._parameter_tree_layout)
        self._parameter_tree_widget = ParameterTree()
        self._parameter_tree_layout.addWidget(self._parameter_tree_widget)

        self._camera_parameter_groups_dictionary = {}
        for webcam_id in self._list_of_available_camera_ids:
            if not webcam_id in dictionary_of_webcam_configs:

                self._camera_parameter_groups_dictionary[
                    webcam_id
                ] = self._create_webcam_parameter_tree_for_unselected_camera(webcam_id)
            else:
                self._camera_parameter_groups_dictionary[
                    webcam_id
                ] = self._create_webcam_parameter_tree(
                    dictionary_of_webcam_configs[webcam_id]
                )

            self._parameter_tree_widget.addParameters(
                self._camera_parameter_groups_dictionary[webcam_id]
            )

        self.camera_parameters_updated_signal.emit(dictionary_of_webcam_configs)

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
                        rotate_video_cv2_code=rotate_image_str_to_cv2_code(
                            camera_parameter_group.param("Rotate Image").value()
                        ),
                    )
                except Exception as e:
                    logger.error(
                        f"Problem creating webcam config from parameter tree for camera: {camera_id} "
                    )
                    raise e

        return new_camera_configs_dict

    def _create_webcam_parameter_tree(self, webcam_config: WebcamConfig):
        try:
            rotate_video_value = rotate_cv2_code_to_str(
                webcam_config.rotate_video_cv2_code
            )
        except KeyError:
            rotate_video_value = "None"

        return Parameter.create(
            name="Camera_" + str(webcam_config.webcam_id),
            type="group",
            children=[
                dict(name="Use this camera?", type="bool", value=True),
                dict(
                    name="Rotate Image",
                    type="list",
                    limits=["None", "90_clockwise", "90_counterclockwise", "180"],
                    value=rotate_video_value,
                ),
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
