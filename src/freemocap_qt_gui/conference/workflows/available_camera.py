from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QWidget

from src.cameras.capture.opencv_camera.opencv_camera import OpenCVCamera
from src.config.webcam_config import WebcamConfig


class AvailableCamera(QWidget):

    def __init__(self, camera_name: str = "0"):
        super().__init__()
        self._camera_name = camera_name

        name_layout = QHBoxLayout()
        name_layout.setSpacing(20)
        name_layout.addWidget(self._create_checkbox())
        name_layout.addWidget(self._create_title())
        name_layout.addWidget(self._create_preview_button())

        self.setLayout(name_layout)

    def _create_title(self):
        camera_title = QLabel(f"Camera {self._camera_name}")
        return camera_title

    def _create_checkbox(self):
        show_hide_checkbox = QCheckBox()
        show_hide_checkbox.setChecked(True)
        return show_hide_checkbox

    def _create_preview_button(self):
        preview = QPushButton("Preview")
        preview.clicked.connect(self._show)
        return preview

    def _show(self):
        cam = OpenCVCamera(
            WebcamConfig()
        )
        cam.connect()
        cam.start_frame_capture_thread()

        cam.show()
