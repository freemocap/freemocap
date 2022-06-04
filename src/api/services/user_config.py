import json
from pathlib import Path

from pydantic import BaseModel

from src.config.home_dir import get_session_path


class WebcamConfigModel(BaseModel):
    webcam_id: str = '0'
    exposure: int = -6
    resolution_width: int = 800
    resolution_height: int = 600


def get_camera_name(camera_id: str):
    return "camera_" + camera_id


class UserConfigService:
    """take things like WebcamConfigModel and save it to a text file or whatever"""

    def save_webcam_config_to_disk(self, webcam_config_model: WebcamConfigModel, session_id: str):
        webcam_config_json = webcam_config_model.json()
        camera_name = get_camera_name(webcam_config_model.webcam_id)
        json_file_name = camera_name + '_config.json'
        session_path = get_session_path(session_id)
        webcam_config_json_path = Path(session_path) / json_file_name
        with open(webcam_config_json_path, 'w') as outfile:
            outfile.write(str(webcam_config_json))
        return webcam_config_json

    def webcam_config_by_id(self, webcam_id: str, session_id: str) -> WebcamConfigModel:
        print(f"webcam id: {webcam_id}")
        session_path = get_session_path(session_id)
        camera_name = get_camera_name(webcam_id)
        print(f"webcam id (again): {webcam_id}")
        print(f"camera name: {camera_name}")
        json_file_name = camera_name + '_config.json'
        webcam_config_json_path = Path(session_path) / json_file_name
        print(f'webcam_config_path: {webcam_config_json_path}')
        webcam_config_model = WebcamConfigModel.parse_file(webcam_config_json_path)
        return webcam_config_model
