import logging
from dataclasses import dataclass

import numpy as np

from src.cameras.capture.opencv_camera.opencv_camera import OpenCVCamera
from src.core_processor.camera_calibration.lens_distortion_calibrator import LensDistortionCalibrator, \
    LensDistortionCalibrationData

logger = logging.getLogger(__name__)


class CameraCalibrator:
    def __init__(self):
        self.lens_distortion_calibrator = LensDistortionCalibrator()

    def calibrate(self, this_camera: OpenCVCamera):
        annotated_image = self.lens_distortion_calibrator.process_incoming_frame(this_camera.latest_frame)
        # add something something cameras 6DoF calibration stuff here later

        return annotated_image
