from typing import NamedTuple, Union

import numpy as np


class FramePayload(NamedTuple):
    success: bool = False
    image: np.ndarray = None
    timestamp: Union[int, float] = None
    frame_number: int = None
    webcam_id: str = None


