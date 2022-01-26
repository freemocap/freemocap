import cv2
from pydantic import BaseModel

from freemocap.prod.cam.cam_detection import DetectPossibleCameras


class OpenCVCameraOptions(BaseModel):
    port_number: int
    exposure: int = -5
    resolution_width: int = 1280
    resolution_height: int = 720


# # OpenCV Implementation of interacting with a camera
class OpenCVCamera:

    def __init__(self, options: OpenCVCameraOptions):
        self._options = options

    def connect(self):
        c = DetectPossibleCameras()
        available_cameras = c.find_available_cameras()


