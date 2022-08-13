from typing import List

from pydantic import BaseModel


class AppState(BaseModel):
    session_id: str = None
    available_cameras: List[str] = []
    selected_cameras: List[str] = []
    camera_configs: dict = (
        {}
    )  # TODO - make this a dict of `WebcamConfigs`, but I don't know how to make Pydantic `accept_arbitraty_types`
    main_window_height: int = None
    main_window_width: int = None
    use_previous_calibration: bool = False


APP_STATE = AppState()
