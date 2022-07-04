from functools import partial

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.cameras.detection.models import FoundCamerasResponse
from src.freemocap_qt_gui.conference.qt_utils.clear_layout import clearLayout
from src.freemocap_qt_gui.conference.workflows.available_camera import AvailableCamera
from src.freemocap_qt_gui.refactored_gui.workers.cam_detection_thread import CamDetectionWorker


class AvailableCamerasList(QWidget):
    PreviewClick = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._worker = CamDetectionWorker()
        self._worker.finished.connect(self._clear_and_add_widgets)

        container = QVBoxLayout()

        title_layout = QHBoxLayout()
        avail_cam_title = QLabel("Available Cameras")
        self._detect_button = self._create_refresh_button()

        title_layout.addWidget(avail_cam_title)
        title_layout.addWidget(self._detect_button)
        title_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._camera_list_layout = QVBoxLayout()
        self._camera_list_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        container.addLayout(title_layout)
        container.addLayout(self._camera_list_layout)

        self.setLayout(container)

    @property
    def get_checked_cameras(self):
        selected_cameras = []
        for cam_widget in self._current_cam_widgets:
            if cam_widget.show_cam_checkbox.isChecked():
                selected_cameras.append(cam_widget.webcam_id)
        return selected_cameras

    @property
    def detect(self):
        return self._detect_button

    def _create_refresh_button(self):
        refresh_button = QPushButton("Detect")
        refresh_button.clicked.connect(self._detect)
        return refresh_button

    def _detect(self):
        if self._worker.isRunning():
            return
        self._worker.start()

    def _create_available_camera_widgets(self, detected: FoundCamerasResponse):
        camera_widgets = []
        for cam in detected.cameras_found_list:
            available_cam = AvailableCamera(cam.webcam_id)
            available_cam.preview.clicked.connect(
                partial(self._handle_camera_preview_click, cam.webcam_id)
            )
            camera_widgets.append(available_cam)

        return camera_widgets

    def _clear_and_add_widgets(self, detected: FoundCamerasResponse):
        clearLayout(self._camera_list_layout)
        current_cam_widgets = self._create_available_camera_widgets(detected)
        for widget in current_cam_widgets:
            self._camera_list_layout.addWidget(widget)

        self._current_cam_widgets = current_cam_widgets

    def _handle_camera_preview_click(self, cam_id):
        self.PreviewClick.emit(cam_id)

