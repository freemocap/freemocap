import json
from pathlib import Path

from pydantic import BaseModel


class WebcamConfigModel(BaseModel):
    webcam_id: str = '0'
    exposure: int = -6
    resolution_width: int = 800
    resolution_height: int = 600
    session_path: str


class UserConfigService:
    """take things like WebcamConfigModel and save it to a text file or whatever"""

    def save_webcam_config_to_disk(self, webcam_config_model: WebcamConfigModel):
        webcam_config_json = webcam_config_model.dict(exclude={'session_path'})
        webcam_config_json_path = Path(webcam_config_model.session_path) / 'webcam_config.json'
        with open(webcam_config_json_path, 'w') as outfile:
            outfile.write(str(webcam_config_json))
        return webcam_config_json
