import enum
import logging

from PyQt6 import QtGui
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from old_src.cameras.webcam_config import WebcamConfig
from old_src.gui.main.workers.cam_charuco_frame_thread_worker import (
    CamCharucoFrameThreadWorker,
)
from old_src.gui.main.workers.cam_frame_worker import CamFrameWorker

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


class SingleCameraWidget(QWidget):
    started = pyqtSignal()

    def __init__(self, webcam_config: WebcamConfig):
        super().__init__()
        self._webcam_config = webcam_config

        layout = QVBoxLayout()
        self.setLayout(layout)

        self._camera_name_str = f"Camera {self._webcam_config.webcam_id}"
        layout.addWidget(QLabel(self._camera_name_str))

        self._video_label = QLabel()
        self._video_label.setFrameStyle((QFrame.Panel | QFrame.Plain))
        self._video_label.setLineWidth(3)
        # self._video.setScaledContents(True)

        layout.addWidget(self._video_label)

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

    def _handle_image_update(self, q_image):
        self._pixmap = QPixmap.fromImage(q_image)

        if (
            self._video_label.width() < self._webcam_config.resolution_width
            or self._video_label.height() < self._webcam_config.resolution_height
        ):
            scaled_width = self._video_label.width()
            scaled_height = self._video_label.height()
        else:
            scaled_width = self._webcam_config.resolution_width
            scaled_height = self._webcam_config.resolution_height

        self._pixmap = self._pixmap.scaled(
            scaled_width,
            scaled_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

        self._video_label.setPixmap(self._pixmap)

    # def resizeEvent(self, a0: QtGui.QResizeEvent) -> None:
    #     logging.info(f" Camera {self._webcam_config.webcam_id} window resized")

    # TO DO - Some kinda something here to make the videos scale properly and keep their aspect ratio

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        logging.info(f" Camera {self._webcam_config.webcam_id} window closed")
        self._worker.quit()
