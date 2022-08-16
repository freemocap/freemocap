import cv2
from PyQt6.QtWidgets import QVBoxLayout, QWidget, QPushButton, QComboBox, QLabel
from pyqtgraph.parametertree import ParameterTree, Parameter

from src.config.webcam_config import WebcamConfig
from src.gui.main.app_state.app_state import APP_STATE
from src.gui.main.qt_utils.clear_layout import clear_layout

rotate_image_str_to_cv2_dict = {
    "None": None,
    "90_clockwise": cv2.ROTATE_90_CLOCKWISE,
    "90_counterclockwise": cv2.ROTATE_90_COUNTERCLOCKWISE,
    "180": cv2.ROTATE_180,
}


def find_rotate_video_value(rotate_video_value):
    if rotate_video_value is None:
        return None
    elif rotate_video_value == cv2.ROTATE_90_CLOCKWISE:
        return "90_clockwise"
    elif rotate_video_value == cv2.ROTATE_90_COUNTERCLOCKWISE:
        return "90_counterclockwise"
    elif rotate_video_value == cv2.ROTATE_180:
        return "180"


class CameraSetupControlPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._panel_layout = QVBoxLayout()
        self.setLayout(self._panel_layout)

        self._redetect_cameras_button = QPushButton(
            "TO-DO - Re-Detect Cameras",
        )
        self._redetect_cameras_button.setEnabled(False)
        self._panel_layout.addWidget(self._redetect_cameras_button)

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

    @property
    def redetect_cameras_button(self):
        return self._redetect_cameras_button

    def update_camera_configs(self):
        clear_layout(self._parameter_tree_layout)
        self._parameter_tree_layout = QVBoxLayout()
        self._parameter_tree_widget = ParameterTree()
        self._parameter_tree_layout.addWidget(self._parameter_tree_widget)

        self._camera_parameter_groups_dict = {}
        for webcam_id in APP_STATE.available_cameras:

            if webcam_id in APP_STATE.camera_configs:
                self._camera_parameter_groups_dict[
                    webcam_id
                ] = self._create_webcam_parameter_tree(
                    APP_STATE.camera_configs[webcam_id]
                )

            else:
                self._camera_parameter_groups_dict[
                    webcam_id
                ] = self._create_webcam_parameter_tree_for_unselected_camera(webcam_id)

            self._parameter_tree_widget.addParameters(
                self._camera_parameter_groups_dict[webcam_id]
            )

        self._apply_settings_to_cameras_button.setEnabled(True)

        self._panel_layout.addWidget(self._parameter_tree_widget)

    def _create_webcam_parameter_tree(self, webcam_config: WebcamConfig):

        try:
            rotate_video_value = find_rotate_video_value(
                APP_STATE.rotate_videos_dict[webcam_config.webcam_id]
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

    def save_settings_to_app_state(self):
        new_selected_cameras_list = []
        new_camera_configs_dict = {}

        for (
            camera_id,
            camera_parameter_group,
        ) in self._camera_parameter_groups_dict.items():
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
                    APP_STATE.rotate_videos_dict[camera_id] = (
                        rotate_image_str_to_cv2_dict[
                            camera_parameter_group.param("Rotate Image").value()
                        ],
                    )
                except:
                    new_camera_configs_dict[camera_id] = WebcamConfig(
                        webcam_id=camera_id
                    )

        APP_STATE.selected_cameras = new_selected_cameras_list
        APP_STATE.camera_configs = new_camera_configs_dict
