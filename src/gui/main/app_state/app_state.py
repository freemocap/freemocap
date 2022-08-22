from typing import List

from pydantic import BaseModel


class AppState(BaseModel):
    session_id: str = None
    available_cameras: List[str] = []
    selected_cameras: List[str] = []
    camera_configs: dict = {}
    main_window_height: int = None
    main_window_width: int = None
    use_previous_calibration: bool = False
    rotate_videos_dict: dict = {}


APP_STATE = AppState()
