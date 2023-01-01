from dataclasses import dataclass

import numpy as np

from old_src.cameras.capture.dataclasses.frame_payload import FramePayload
from old_src.core_processes.capture_volume_calibration.charuco_board_detection.dataclasses.charuco_view_data import (
    CharucoViewData,
)


@dataclass
class CharucoFramePayload:
    raw_frame_payload: FramePayload = FramePayload()
    annotated_image: np.ndarray = None
    charuco_view_data: CharucoViewData = CharucoViewData()
