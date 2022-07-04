from typing import List

from pydantic import BaseModel


class AppState(BaseModel):
    session_id: str = None
    selected_cameras: List[str] = []


APP_STATE = AppState()
