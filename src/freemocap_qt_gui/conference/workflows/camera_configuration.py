from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.freemocap_qt_gui.conference.workers.cam_frame_worker import CamFrameWorker
from src.freemocap_qt_gui.conference.workflows.available_cameras_list import AvailableCamerasList


class CameraConfiguration(QWidget):

    def __init__(self):
        super().__init__()
        # Holds the Camera Configuration Title
        container = QVBoxLayout()
        self._worker = CamFrameWorker()
        self._worker.ImageUpdate.connect(self._handle_image_update)

        config_title_layout = QHBoxLayout()

        cam_cfg_title = QLabel("Camera Configuration")
        config_title_layout.addWidget(cam_cfg_title)

        # Shows the cameras that can be selected, and shows previews(TODO)
        camera_and_preview_container = QHBoxLayout()
        list_widget = self._create_available_cams_widget()
        self._video = self._create_preview_image()
        camera_and_preview_container.addWidget(list_widget)
        camera_and_preview_container.addWidget(self._video)

        # Holds the Accept Button
        accept_container = QHBoxLayout()
        accept_button = QPushButton("Accept")
        accept_container.addWidget(accept_button)

        container.addLayout(config_title_layout)
        container.addLayout(camera_and_preview_container)
        container.addLayout(accept_container)

        self.setLayout(container)

    def _create_available_cams_widget(self):
        list_widget = AvailableCamerasList()
        list_widget.PreviewClick.connect(self._create_preview_worker)
        return list_widget

    def _create_preview_image(self):
        video_preview = QLabel()
        return video_preview

    def _create_preview_worker(self, cam_id):
        if self._worker.isRunning():
            self._worker.quit()
        self._worker._cam_id = cam_id
        self._worker.start()

    def _handle_image_update(self, image):
        self._video.setPixmap(QPixmap.fromImage(image))
