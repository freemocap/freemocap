from typing import Union, List

import cv2
from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QImage

from src.cameras.capture.dataclasses.frame_payload import FramePayload
from src.cameras.capture.opencv_camera.opencv_camera import OpenCVCamera
from src.cameras.persistence.video_writer.video_recorder import VideoRecorder
from src.config.webcam_config import WebcamConfig
from src.pipelines.calibration_pipeline.charuco_board_detection.charuco_board_detector import (
    CharucoBoardDetector,
)

import logging

logger = logging.getLogger(__name__)


class CamCharucoFrameThreadWorker(QThread):
    image_updated_signal = pyqtSignal(QImage)
    ready_to_save_to_video = pyqtSignal(VideoRecorder)

    def __init__(self, webcam_config: WebcamConfig):
        super().__init__()
        self._charuco_board_detector = CharucoBoardDetector()
        self._video_recorder = VideoRecorder()
        self._webcam_config = webcam_config
        self._should_save_frames = False
        self._should_continue = True
        self._saved_frame_list = []

    @property
    def should_save_frames(self):
        return self._should_save_frames

    @property
    def video_recorder(self):
        return self._video_recorder

    def start_saving_frames(self):
        self._should_save_frames = True

    def stop_saving_frames(self):
        self._should_save_frames = False

    def run(self):

        open_cv_camera = OpenCVCamera(self._webcam_config)
        open_cv_camera.connect()
        open_cv_camera.start_frame_capture_thread()

        self._open_cv_camera = open_cv_camera
        self._should_continue = True
        any_frames_recorded = False
        try:
            while open_cv_camera.is_capturing_frames and self._should_continue:
                if not open_cv_camera.new_frame_ready:
                    continue
                frame_payload = open_cv_camera.latest_frame

                if self._should_save_frames:
                    any_frames_recorded = True
                    print("saving frame :D")
                    self._video_recorder.append_frame_payload_to_list(frame_payload)

                charuco_payload = (
                    self._charuco_board_detector.detect_charuco_board_in_frame_payload(
                        frame_payload
                    )
                )
                image_to_display = charuco_payload.annotated_image
                image_to_display = cv2.flip(image_to_display, 1)
                image_to_display = cv2.cvtColor(image_to_display, cv2.COLOR_BGR2RGB)
                converted_frame = QImage(
                    image_to_display.data,
                    image_to_display.shape[1],
                    image_to_display.shape[0],
                    QImage.Format.Format_RGB888,
                )
                converted_frame = converted_frame.scaledToHeight(300)

                self.image_updated_signal.emit(converted_frame)
        finally:
            logger.info(f"Closing Camera {self._open_cv_camera.webcam_id_as_str}")
            self._open_cv_camera.close()

    def quit(self):
        self._open_cv_camera.close()
        super().quit()
