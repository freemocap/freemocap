from typing import List

from pydantic import BaseModel


class FoundCamerasResponse(BaseModel):
    number_of_cameras_found: int
    list_of_usb_port_numbers_with_cameras_attached: List[int]
    cv2_backend: int
