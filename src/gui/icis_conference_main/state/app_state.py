from typing import List

from pydantic import BaseModel


class AppState(BaseModel):
    session_id: str = None
    selected_cameras: List[str] = []
    use_previous_calibration: bool = False
    number_of_frames_in_the_mocap_videos: int = None


APP_STATE = AppState()
