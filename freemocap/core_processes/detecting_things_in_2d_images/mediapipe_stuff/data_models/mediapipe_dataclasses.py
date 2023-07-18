import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
from skellycam.detection.models.frame_payload import FramePayload

logger = logging.getLogger(__name__)


@dataclass
class Mediapipe2dNumpyArrays:
    body_frameNumber_trackedPointNumber_XYZ: np.ndarray = None
    body_world_frameNumber_trackedPointNumber_XYZ: np.ndarray = None
    rightHand_frameNumber_trackedPointNumber_XYZ: np.ndarray = None
    leftHand_frameNumber_trackedPointNumber_XYZ: np.ndarray = None
    face_frameNumber_trackedPointNumber_XYZ: np.ndarray = None

    body_frameNumber_trackedPointNumber_confidence: np.ndarray = None

    @property
    def has_data(self):
        return not np.isnan(self.body_frameNumber_trackedPointNumber_XYZ).all()

    @property
    def all_data2d_nFrames_nTrackedPts_XY(self):
        """dimensions will be [number_of_frames , number_of_markers, XY]"""

        if self.body_frameNumber_trackedPointNumber_XYZ is None:
            # if there's no body data, there's no hand or face data either
            return

        if len(self.body_frameNumber_trackedPointNumber_XYZ.shape) == 3:  # multiple frames
            return np.hstack(
                [
                    self.body_frameNumber_trackedPointNumber_XYZ,
                    self.rightHand_frameNumber_trackedPointNumber_XYZ,
                    self.leftHand_frameNumber_trackedPointNumber_XYZ,
                    self.face_frameNumber_trackedPointNumber_XYZ,
                ]
            )
        elif len(self.body_frameNumber_trackedPointNumber_XYZ.shape) == 2:  # single frame
            return np.vstack(
                [
                    self.body_frameNumber_trackedPointNumber_XYZ,
                    self.rightHand_frameNumber_trackedPointNumber_XYZ,
                    self.leftHand_frameNumber_trackedPointNumber_XYZ,
                    self.face_frameNumber_trackedPointNumber_XYZ,
                ]
            )
        else:
            logger.error("data should have either 2 or 3 dimensions")


@dataclass
class Mediapipe2dDataPayload:
    raw_frame_payload: FramePayload = None
    mediapipe_results: Any = None
    annotated_image: np.ndarray = None
    pixel_data_numpy_arrays: Mediapipe2dNumpyArrays = None
