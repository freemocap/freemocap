import logging
from dataclasses import dataclass

import numpy as np

from src.pipelines.calibration_pipeline.charuco_board_detection.dataclasses.charuco_board_definition import CharucoBoardDataClass

logger = logging.getLogger(__name__)


@dataclass
class CharucoViewData:
    charuco_board_object: CharucoBoardDataClass = None  # the charuco board definition this 'view' was trying to detect
    charuco_corners: np.ndarray = None
    charuco_ids: np.ndarray = None
    aruco_square_corners: np.ndarray = None
    aruco_square_ids: np.ndarray = None
    full_board_found: bool = False
    some_charuco_corners_found: bool = False
    any_markers_found: bool = False
    image_width: int = None
    image_height: int = None

    def __post_init__(self):
        if self.some_charuco_corners_found:
            if self.some_charuco_corners_found:
                if self.charuco_board_object is None:
                    logger.warning(
                        'If there is any data in this view point, you should also include a copy of the charcuo_board that was being detected')
