import enum

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget, QSizePolicy

from src.config.webcam_config import WebcamConfig
from src.gui.main.workers.cam_charuco_frame_thread_worker import (
    CamCharucoFrameThreadWorker,
)
from src.gui.main.workers.cam_frame_worker import CamFrameWorker

import logging

logger = logging.getLogger(__name__)


class WorkerType(enum.Enum):
    FRAME_CAPTURE = 0
    CHARUCO = 1


def construct_worker(worker_type: WorkerType):
    if worker_type.CHARUCO:
        return CamCharucoFrameThreadWorker

    if worker_type.FRAME_CAPTURE:
        return CamFrameWorker

    raise Exception("What?")


class CameraWidget(QWidget):
    started = pyqtSignal()

    def __init__(self, webcam_config: WebcamConfig):
        super().__init__()
        self._webcam_config = webcam_config
        self._video = QLabel()
        # self._video.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        layout = QHBoxLayout()
        layout.addWidget(self._video)

        self.setLayout(layout)

    @property
    def camera_id(self):
        return self._webcam_config.webcam_id

    @property
    def should_record_frames(self):
        return self._worker.should_save_frames

    @property
    def video_recorder(self):
        return self._worker.video_recorder

    @property
    def opencv_camera_is_open(self):
        return self._worker.opencv_camera_is_open

    def start(self):
        self._worker = self._init_frame_worker()
        self._worker.start()
        self.started.emit()

    def quit(self):
        self._worker.quit()

    def start_saving_frames(self):
        self._worker.start_saving_frames()

    def stop_saving_frames(self):
        self._worker.stop_saving_frames()

    def reset_video_recorder(self):
        self._worker.reset_video_recorder()

    def _init_frame_worker(self):
        worker = construct_worker(WorkerType.CHARUCO)(self._webcam_config)
        worker.image_updated_signal.connect(self._handle_image_update)
        return worker

    def _handle_image_update(self, image):
        self._video.setPixmap(QPixmap.fromImage(image))
