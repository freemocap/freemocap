from typing import List

from pydantic import BaseModel


class RawCamera(BaseModel):
    webcam_id: str


class FoundCamerasResponse(BaseModel):
    number_of_cameras_found: int
    cameras_found: List[RawCamera]
    cv2_backend: int
