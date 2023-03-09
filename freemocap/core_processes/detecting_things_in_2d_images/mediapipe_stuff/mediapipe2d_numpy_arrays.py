import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)
@dataclass
class Mediapipe2dNumpyArrays:
    body2d_frameNumber_trackedPointNumber_XY: np.ndarray = None
    rightHand2d_frameNumber_trackedPointNumber_XY: np.ndarray = None
    leftHand2d_frameNumber_trackedPointNumber_XY: np.ndarray = None
    face2d_frameNumber_trackedPointNumber_XY: np.ndarray = None

    body2d_frameNumber_trackedPointNumber_confidence: np.ndarray = None

    @property
    def has_data(self):
        return not np.isnan(self.body2d_frameNumber_trackedPointNumber_XY).all()

    @property
    def all_data2d_nFrames_nTrackedPts_XY(self):
        """dimensions will be [number_of_frames , number_of_markers, XY]"""

        if self.body2d_frameNumber_trackedPointNumber_XY is None:
            # if there's no body data, there's no hand or face data either
            return

        if len(self.body2d_frameNumber_trackedPointNumber_XY.shape) == 3:  # multiple frames
            return np.hstack(
                [
                    self.body2d_frameNumber_trackedPointNumber_XY,
                    self.rightHand2d_frameNumber_trackedPointNumber_XY,
                    self.leftHand2d_frameNumber_trackedPointNumber_XY,
                    self.face2d_frameNumber_trackedPointNumber_XY,
                ]
            )
        elif len(self.body2d_frameNumber_trackedPointNumber_XY.shape) == 2:  # single frame
            return np.vstack(
                [
                    self.body2d_frameNumber_trackedPointNumber_XY,
                    self.rightHand2d_frameNumber_trackedPointNumber_XY,
                    self.leftHand2d_frameNumber_trackedPointNumber_XY,
                    self.face2d_frameNumber_trackedPointNumber_XY,
                ]
            )
        else:
            logger.error("data should have either 2 or 3 dimensions")
