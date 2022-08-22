import cv2
from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QImage

from src.cameras.capture.opencv_camera.opencv_camera import OpenCVCamera
from src.cameras.persistence.video_writer.video_recorder import VideoRecorder
from src.config.webcam_config import WebcamConfig
from src.gui.main.app_state.app_state import APP_STATE
from src.pipelines.calibration_pipeline.charuco_board_detection.charuco_board_detector import (
    CharucoBoardDetector,
)


class CamCharucoFrameWorker(QThread):
    ImageUpdate = pyqtSignal(QImage)

    def __init__(
        self,
        cam_id=None,
        should_save_frames: bool = False,
    ):
        super().__init__()
        self._charuco_board_detector = CharucoBoardDetector()
        self._cam_id = cam_id
        self._video_recorder = VideoRecorder()
        self._should_save_frames = should_save_frames
        self._should_continue = True

    @property
    def should_save_frames(self):
        return self._should_save_frames

    @should_save_frames.setter
    def should_save_frames(self, value):
        self._should_save_frames = value

    @property
    def video_recorder(self):
        return self._video_recorder

    def start_recording(self):
        self._should_save_frames = True

    def stop_recording(self):
        self._should_save_frames = False
        self._should_continue = False

    def run(self):
        camera_config = APP_STATE.camera_configs[self._cam_id]
        open_cv_camera = OpenCVCamera(
            camera_config,
            session_id=APP_STATE.session_id,
        )
        open_cv_camera.connect()
        open_cv_camera.start_frame_capture_thread()

        self._open_cv_camera = open_cv_camera
        self._should_continue = True
        try:
            while open_cv_camera.is_capturing_frames and self._should_continue:
                if not open_cv_camera.new_frame_ready:
                    continue
                frame_payload = open_cv_camera.latest_frame

                if self._should_save_frames:
                    print("saving frame :D")
                    self._video_recorder.append_frame_payload_to_list(frame_payload)

                charuco_frame_payload = (
                    self._charuco_board_detector.detect_charuco_board_in_frame_payload(
                        frame_payload
                    )
                )
                image_to_display = charuco_frame_payload.annotated_image
                image_to_display = cv2.flip(image_to_display, 1)
                image_to_display = cv2.cvtColor(image_to_display, cv2.COLOR_BGR2RGB)
                converted_frame = QImage(
                    image_to_display.data,
                    image_to_display.shape[1],
                    image_to_display.shape[0],
                    QImage.Format.Format_RGB888,
                )
                converted_frame = converted_frame.scaledToHeight(
                    APP_STATE.main_window_height / len(APP_STATE.selected_cameras)
                )
                self.ImageUpdate.emit(converted_frame)
        finally:
            print(
                f"Closing the camera {self._open_cv_camera.webcam_id_as_str}, and saving video to disk"
            )
            self._open_cv_camera.close()
            # if any_frames_recorded:
            #     print(f"saving video for camera {self._cam.webcam_id_as_str}")
            #     self._cam.video_recorder.save_list_of_frames_to_video_file(calibration_videos=True)
            #     print(f"Saved video to: {str(self._cam.video_recorder.path_to_save_video_file)}")

    def quit(self):
        self._open_cv_camera.close()
        super().quit()
