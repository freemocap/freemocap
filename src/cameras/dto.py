from typing import List, NamedTuple

import numpy as np
from pydantic import BaseModel


class RawCamera(BaseModel):
    webcam_id: str


class FindAvailableResponse(BaseModel):
    camera_found_count: int
    cams_to_use: List[RawCamera]
    cv2_backend: int


class FramePayload(NamedTuple):
    success: bool
    image: np.ndarray
    timestamp: int
