from typing import List

from pydantic import BaseModel


class AppState(BaseModel):
    session_id: str = None
    available_cameras: List[str] = []
    selected_cameras: List[str] = []
    main_window_height: int = None
    main_window_width: int = None


APP_STATE = AppState()
