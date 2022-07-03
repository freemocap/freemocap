import typing

from PyQt6 import QtCore
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.cameras.detection.models import FoundCamerasResponse
from src.freemocap_qt_gui.conference.workflows.available_camera import AvailableCamera


class AvailableCamerasList(QWidget):
    def __init__(
        self,
        detected_cameras: FoundCamerasResponse
    ) -> None:
        super().__init__()
        self._detected = detected_cameras

        container = QVBoxLayout()

        title_layout = QHBoxLayout()
        avail_cam_title = QLabel("Available Cameras")
        refresh_button = QPushButton("Refresh")

        title_layout.addWidget(avail_cam_title)
        title_layout.addWidget(refresh_button)
        title_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        camera_list_layout = QVBoxLayout()
        for widget in self._create_available_camera_widgets():
            camera_list_layout.addWidget(widget)
        camera_list_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        container.addLayout(title_layout)
        container.addLayout(camera_list_layout)

        self.setLayout(container)

    def _create_available_camera_widgets(self):
        detected = self._detected
        camera_widgets = []
        for cam in detected.cameras_found_list:
            available_cam = AvailableCamera(cam.webcam_id)
            camera_widgets.append(available_cam)

        return camera_widgets
