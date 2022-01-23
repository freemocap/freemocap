import cv2
from pydantic import BaseModel


class OpenCVCameraOptions(BaseModel):
    port_number: int
    exposure: int = -5
    resolution_width: int = 1280
    resolution_height: int = 720


# # OpenCV Implementation of interacting with a camera
# class OpenCVCamera:
#
#     def __init__(self, options: OpenCVCameraOptions):
#         self._options = options
#
#     def connect(self):
#         # c = cv2.VideoCapture()
#         cv2.VideoCapture(, cv2.CAP_ANY)
