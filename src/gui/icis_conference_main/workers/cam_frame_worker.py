import cv2
from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QImage

from src.cameras.capture.opencv_camera.opencv_camera import OpenCVCamera
from src.cameras.webcam_config import WebcamConfig


class CamFrameWorker(QThread):
    ImageUpdate = pyqtSignal(QImage)

    def __init__(self, cam_id=None):
        super().__init__()
        self._cam_id = cam_id

    def run(self):
        cam = OpenCVCamera(WebcamConfig(webcam_id=self._cam_id))
        cam.connect()
        cam.start_frame_capture_thread()
        self._cam = cam
        try:
            while cam.is_capturing_frames:
                if not cam.new_frame_ready:
                    continue
                payload = cam.latest_frame

                image = cv2.flip(payload.image, 1)
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                converted_frame = QImage(
                    image.data,
                    image.shape[1],
                    image.shape[0],
                    QImage.Format.Format_RGB888,
                )
                converted_frame = converted_frame.scaled(
                    640, 480, Qt.AspectRatioMode.KeepAspectRatio
                )
                self.ImageUpdate.emit(converted_frame)
        finally:
            print("Closing the camera")
            self._cam.close()

    def quit(self):
        self._cam.close()
        super().quit()
