import enum

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from src.gui.main.app import get_qt_app
from src.gui.main.workers.cam_charuco_frame_worker import CamCharucoFrameWorker
from src.gui.main.workers.cam_frame_worker import CamFrameWorker


class WorkerType(enum.Enum):
    FRAME_CAPTURE = 0
    CHARUCO = 1


def construct_worker(worker_type: WorkerType):
    if worker_type.CHARUCO:
        return CamCharucoFrameWorker

    if worker_type.FRAME_CAPTURE:
        return CamFrameWorker

    raise Exception("What?")


class SingleCameraWidget(QWidget):
    started = pyqtSignal()

    def __init__(self, camera_id):
        super().__init__()
        self._camera_id = camera_id
        self._worker = self._init_frame_worker()
        self._video = QLabel()

        layout = QHBoxLayout()
        layout.addWidget(self._video)

        self.setLayout(layout)

        get_qt_app().aboutToQuit.connect(self.quit)

    @property
    def camera_id(self):
        """short int/str id for this camera"""
        return self._camera_id

    @property
    def should_record_frames(self):
        return self._worker.should_save_frames

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
        worker = construct_worker(WorkerType.CHARUCO)(self._camera_id)
        worker.ImageUpdate.connect(self._handle_image_update)
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
