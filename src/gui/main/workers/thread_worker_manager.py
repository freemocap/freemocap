from src.gui.main.workers.cam_detection_thread_worker import CameraDetectionThreadWorker

import logging

logger = logging.getLogger(__name__)


class ThreadWorkerManager:
    def __init__(self):
        self._camera_detection_thread_worker = CameraDetectionThreadWorker()

    @property
    def camera_detection_thread_worker(self):
        return self._camera_detection_thread_worker

    def launch_detect_cameras_worker(self):
        logger.info("Launch camera detection worker")
        self._camera_detection_thread_worker.start()
