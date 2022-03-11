from typing import List

from pydantic import BaseModel


class RawCamera(BaseModel):
    webcam_id: str


class FoundCamerasResponse(BaseModel):
    camera_found_count: int
    cams_to_use: List[RawCamera]
    cv2_backend: int
