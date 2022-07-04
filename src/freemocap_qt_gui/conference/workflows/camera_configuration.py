import time

from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.freemocap_qt_gui.conference.shared_widgets.page_title import PageTitle
from src.freemocap_qt_gui.conference.workers.cam_frame_worker import CamFrameWorker
from src.freemocap_qt_gui.conference.workflows.available_cameras_list import AvailableCamerasList
from src.freemocap_qt_gui.refactored_gui.state.app_state import APP_STATE


class CameraConfiguration(QWidget):

    def __init__(self):
        super().__init__()
        self._worker = self._init_frame_worker()

        self._accept_button = self._create_accept_button()
        self._accept_button.hide()

        container = QVBoxLayout()

        # Holds the Camera Configuration Title
        config_title_layout = QHBoxLayout()
        cam_cfg_title = PageTitle("Camera Configuration")
        config_title_layout.addWidget(cam_cfg_title)

        # Shows the cameras that can be selected, and shows previews(TODO)
        camera_and_preview_container = QHBoxLayout()
        self._list_widget = self._create_available_cams_widget()
        self._video = self._create_preview_image()
        camera_and_preview_container.addWidget(self._list_widget)
        camera_and_preview_container.addWidget(self._video)

        # Holds the Accept Button
        self._accept_container = QHBoxLayout()
        self._accept_container.addWidget(self._accept_button)

        container.addLayout(config_title_layout)
        container.addLayout(camera_and_preview_container)
        container.addLayout(self._accept_container)

        self.setLayout(container)

    @property
    def config_accepted(self):
        return self._accept_button

    def _init_frame_worker(self):
        worker = CamFrameWorker()
        worker.ImageUpdate.connect(self._handle_image_update)
        return worker

    def _create_accept_button(self):
        accept_button = QPushButton("Accept")
        accept_button.clicked.connect(self._handle_accept_button_click)
        return accept_button

    def _create_available_cams_widget(self):
        list_widget = AvailableCamerasList()
        list_widget.PreviewClick.connect(self._create_preview_worker)
        list_widget.detect.clicked.connect(self._accept_button.show)
        return list_widget

    def _create_preview_image(self):
        video_preview = QLabel()
        return video_preview

    def _create_preview_worker(self, cam_id):
        self._video.clear()
        if self._worker.isRunning():
            self._worker.quit()
            while not self._worker.isFinished():
                time.sleep(.1)

        self._worker._cam_id = cam_id
        self._worker.start()

    def _handle_image_update(self, image):
        self._video.setPixmap(QPixmap.fromImage(image))

    def _handle_accept_button_click(self):
        # Save the selected cameras to app state
        selected_cams = self._list_widget.get_checked_cameras
        APP_STATE.selected_cameras = selected_cams
