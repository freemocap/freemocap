import cv2
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

from src.cameras.capture.dataclasses.frame_payload import FramePayload
from src.cameras.capture.opencv_camera.opencv_camera import OpenCVCamera
from src.cameras.persistence.video_writer.video_recorder import VideoRecorder
from src.config.webcam_config import WebcamConfig
from src.core_processes.capture_volume_calibration.charuco_board_detection.charuco_board_detector import (
    CharucoBoardDetector,
)

import logging

from src.gui.main.app_state.app_state import APP_STATE

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

    @property
    def opencv_camera_is_open(self):
        return self._open_cv_camera.is_open

    def start_saving_frames(self):
        self._should_save_frames = True

    def stop_saving_frames(self):
        self._should_save_frames = False

    def reset_video_recorder(self):
        self._video_recorder = VideoRecorder()

    def run(self):
        if hasattr(self, "_open_cv_camera"):
            self._open_cv_camera.release()

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

                if self._webcam_config.rotate_video_cv2_code is not None:
                    rotated_image = cv2.rotate(
                        frame_payload.image,
                        self._webcam_config.rotate_video_cv2_code,
                    )
                    frame_payload = FramePayload(
                        success=frame_payload.success,
                        image=rotated_image,
                        timestamp_in_seconds_from_record_start=frame_payload.timestamp_in_seconds_from_record_start,
                        timestamp_unix_time_seconds=frame_payload.timestamp_unix_time_seconds,
                        frame_number=frame_payload.frame_number,
                        webcam_id=frame_payload.webcam_id,
                    )

                if self._should_save_frames:
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
                converted_frame = converted_frame.scaledToHeight(
                    APP_STATE.main_window_height / 2  # len(APP_STATE.available_cameras)
                )

                self.image_updated_signal.emit(converted_frame)
        finally:
            logger.info(f"Closing Camera {self._open_cv_camera.webcam_id_as_str}")
            self._open_cv_camera.close()

    def quit(self):
        self._should_continue = False
        try:
            self._open_cv_camera.close()
        except Exception as e:
            print(e)
        super().quit()
