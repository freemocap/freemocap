from dataclasses import dataclass
from typing import List

import numpy as np

from src.cameras.capture.frame_payload import FramePayload
from src.core_processor.camera_calibration.lens_distortion_calibrator import LensDistortionCalibrator, \
    LensDistortionCalibrationData


@dataclass
class CameraCalibrationData:
    image_width: int
    image_height: int
    lens_distortion_calibration_data: LensDistortionCalibrationData = None
    camera_translation_relative_to_camera0: np.ndarray = np.zeros((3, 1))
    camera_rotation_relative_to_camera0: np.ndarray = np.zeros((3, 1))

    def __init__(self, image_width, image_height):
        self.image_width = image_width
        self.image_height = image_height
        self.lens_distortion_calibration_data = LensDistortionCalibrationData(self.image_width,
                                                                              self.image_height)


class CameraCalibrator:
    def __init__(self,
                 lens_distortion_calibrator: LensDistortionCalibrator = LensDistortionCalibrator()
                 ):
        self._lens_distortion_calibrator = lens_distortion_calibrator

    def calibrate(self, this_frame: FramePayload):
        self.calibrate_lens_distortion(this_frame)
        # something something cameras 6DoF

    def calibrate_lens_distortion(self, this_frame):
        self._lens_distortion_calibrator.process_incoming_frame(this_frame)
