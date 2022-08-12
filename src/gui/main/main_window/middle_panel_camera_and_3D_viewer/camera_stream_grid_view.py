import numpy as np
from PyQt6.QtWidgets import QWidget, QGridLayout, QVBoxLayout

from src.gui.main.app_state.app_state import APP_STATE
from src.gui.main.custom_widgets.single_camera_widget import SingleCameraWidget


class CameraStreamGridView(QWidget):
    def __init__(self):
        super().__init__()
        selected_cameras = APP_STATE.selected_cameras

        camera_stream_layout = QVBoxLayout()
        self.setLayout(camera_stream_layout)

        self._camera_widgets = []
        for webcam_id in selected_cameras:
            single_cam_widget = SingleCameraWidget(webcam_id)
            single_cam_widget.capture()
            camera_stream_layout.addWidget(single_cam_widget)
            self._camera_widgets.append(single_cam_widget)
