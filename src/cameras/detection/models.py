from typing import List

from pydantic import BaseModel


class FoundCamerasResponse(BaseModel):
    number_of_cameras_found: int
    cameras_found_list: List[str]
    cv2_backend: int
