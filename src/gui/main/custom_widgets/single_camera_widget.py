import enum

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from src.config.webcam_config import WebcamConfig
from src.gui.main.app import get_qt_app
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
        logger.info(f"Creating camera widget with WebcamConfig: {webcam_config}")
        super().__init__()
        self._webcam_config = webcam_config

        self._worker = self._init_frame_worker()
        self._video = QLabel()

        layout = QHBoxLayout()
        layout.addWidget(self._video)

        self.setLayout(layout)

        get_qt_app().aboutToQuit.connect(self.quit)

    @property
    def should_record_frames(self):
        return self._worker.should_save_frames

    @should_record_frames.setter
    def should_record_frames(self, value):
        self._worker.should_save_frames = value

    @property
    def video_recorder(self):
        return self._worker.video_recorder

    def start_recording(self):
        self._worker.start_recording()

    def stop_recording(self):
        self._worker.stop_recording()

    def capture(self):
        self._create_preview_worker()
        self.started.emit()

    def quit(self):
        self._worker.quit()

    def _init_frame_worker(self):
        worker = construct_worker(WorkerType.CHARUCO)(self._webcam_config)
        worker.image_updated_signal.connect(self._handle_image_update)
        return worker

    def _create_preview_worker(self):
        # self._video.clear()
        # if self._worker.isRunning():
        #     self._worker.quit()
        #     while not self._worker.isFinished():
        #         time.sleep(.1)
        self._worker.start()

    def _handle_image_update(self, image):
        self._video.setPixmap(QPixmap.fromImage(image))
