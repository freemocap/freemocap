from pathlib import Path

from pydantic import BaseModel


def _get_home_dir():
    return str(Path.home())


class WebcamConfig(BaseModel):
    webcam_id: int = 0
    exposure: int = -6
    resolution_width: int = 800
    resolution_height: int = 600
    save_video: bool = False
    # fourcc: str = "MP4V"
    fourcc: str = "MJPG"
    base_save_video_dir = _get_home_dir()
