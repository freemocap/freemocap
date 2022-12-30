from pydantic import BaseModel

from src.config.home_dir import os_independent_home_dir


class WebcamConfig(BaseModel):
    webcam_id: int = 0
    exposure: int = -7
    resolution_width: int = 1280
    resolution_height: int = 720
    # fourcc: str = "MP4V"
    fourcc: str = "MJPG"
    base_save_video_dir = os_independent_home_dir()
    rotate_video_cv2_code: int = None
