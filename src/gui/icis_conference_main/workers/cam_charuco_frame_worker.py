import cv2
from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QImage

from src.cameras.capture.opencv_camera.opencv_camera import OpenCVCamera
from src.cameras.webcam_config import WebcamConfig
from src.gui.icis_conference_main.state.app_state import APP_STATE
from src.core_processes.capture_volume_calibration.charuco_board_detection.charuco_board_detector import (
    CharucoBoardDetector,
)


class CamCharucoFrameWorker(QThread):
    ImageUpdate = pyqtSignal(QImage)

    def __init__(
        self, cam_id=None, should_save_frames: bool = False, calibration_videos=False
    ):
        super().__init__()
        self._board_thingy = CharucoBoardDetector()
        self._cam_id = cam_id
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
        return self._cam.video_recorder

    def run(self):
        cam = OpenCVCamera(
            WebcamConfig(webcam_id=self._cam_id),
            session_id=APP_STATE.session_id,
        )
        cam.connect()
        cam.start_frame_capture_thread()

        self._cam = cam
        any_frames_recorded = False
        try:
            while cam.is_capturing_frames:
                if not cam.new_frame_ready:
                    continue
                payload = cam.latest_frame

                if self._should_save_frames:
                    any_frames_recorded = True
                    print("saving frame :D")
                    cam.video_recorder.append_frame_payload_to_list(payload)

                charuco_payload = (
                    self._board_thingy.detect_charuco_board_in_frame_payload(payload)
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
                converted_frame = converted_frame.scaled(
                    640, 480, Qt.AspectRatioMode.KeepAspectRatio
                )
                self.ImageUpdate.emit(converted_frame)
        finally:
            print(
                f"Closing the camera {self._cam.webcam_id_as_str}, and saving video to disk"
            )
            self._cam.close()
            # if any_frames_recorded:
            #     print(f"saving video for camera {self._cam.webcam_id_as_str}")
            #     self._cam.video_recorder.save_list_of_frames_to_video_file(calibration_videos=True)
            #     print(f"Saved video to: {str(self._cam.video_recorder.path_to_save_video_file)}")

    def quit(self):
        self._cam.close()
        super().quit()
