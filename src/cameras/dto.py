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
    webcam_id: int
    image: np.ndarray
    timestamp: int


class ImagePayload(NamedTuple):
    frames: List[FramePayload] = None
