from typing import NamedTuple, Union

import numpy as np


class FramePayload(NamedTuple):
    success: bool = False
    image: np.ndarray = None
    timestamp_in_seconds_from_record_start:  float = None
    frame_number: int = None
    webcam_id: str = None


