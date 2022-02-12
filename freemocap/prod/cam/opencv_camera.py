import logging

import cv2
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class OpenCVCameraOptions(BaseModel):
    port_number: int
    exposure: int = -5
    resolution_width: int = 1280
    resolution_height: int = 720
    cv2_backend: int


# # OpenCV Implementation of interacting with a camera
class OpenCVCamera:

    def __init__(self, options: OpenCVCameraOptions):
        self._cam_object = None
        self._options = options

    def connect(self):
        self._cam_object = self._create_cv_cam_object()

    @property
    def cv2_object(self):
        return self._cam_object

    # other methods in this class for manipulating the camera
    def _create_cv_cam_object(self):
        cam_object = cv2.VideoCapture(self._options.port_number, self._options.cv2_backend)
        success, image = cam_object.read()
        if success:
            logger.info(f'Camera found at port number {self._options.port_number}')
            return cam_object
        else:
            error_text = f'Could not connect to a camera at port# {self._options.port_number}'
            logger.error(error_text)
            raise SystemError(error_text)
