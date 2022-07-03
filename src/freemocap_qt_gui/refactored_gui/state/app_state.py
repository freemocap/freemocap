from pydantic import BaseModel


class AppState(BaseModel):
    session_id: str = None


APP_STATE = AppState()
