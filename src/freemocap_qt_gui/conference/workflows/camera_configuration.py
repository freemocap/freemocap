from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.cameras.detection.models import FoundCamerasResponse
from src.freemocap_qt_gui.conference.workflows.available_cameras_list import AvailableCamerasList


class CameraConfiguration(QWidget):

    def __init__(self, detected_cameras: FoundCamerasResponse):
        super().__init__()
        self._detected = detected_cameras
        # Holds the Camera Configuration Title
        container = QVBoxLayout()

        config_title_layout = QHBoxLayout()

        cam_cfg_title = QLabel("Camera Configuration")
        config_title_layout.addWidget(cam_cfg_title)

        # Shows the cameras that can be selected, and shows previews(TODO)
        camera_and_preview_container = QHBoxLayout()
        list_widget = AvailableCamerasList(detected_cameras)
        camera_and_preview_container.addWidget(list_widget)

        # Holds the Accept Button
        accept_container = QHBoxLayout()
        accept_button = QPushButton("Accept")
        accept_container.addWidget(accept_button)

        container.addLayout(config_title_layout)
        container.addLayout(camera_and_preview_container)
        container.addLayout(accept_container)

        self.setLayout(container)
