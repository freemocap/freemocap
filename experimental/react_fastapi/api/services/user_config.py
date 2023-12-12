import logging
from pathlib import Path

from pydantic import BaseModel
from src.config.home_dir import get_session_folder_path

logger = logging.getLogger(__name__)


class WebcamConfigModel(BaseModel):
    webcam_id: str
    exposure: int = -6
    resolution_width: int = 1280
    resolution_height: int = 720


def get_camera_name(camera_id: str):
    return "camera_" + camera_id


class UserConfigService:
    """take things like WebcamConfigModel and save it to a text file or whatever"""

    def save_webcam_config_to_disk(
            self, webcam_config_model: WebcamConfigModel, session_id: str
    ):
        webcam_config_json = webcam_config_model.json()
        camera_name = get_camera_name(webcam_config_model.webcam_id)
        json_file_name = camera_name + "_config.json"
        session_path = get_session_folder_path(session_id)
        webcam_config_json_path = Path(session_path) / json_file_name
        with open(webcam_config_json_path, "w") as outfile:
            outfile.write(str(webcam_config_json))
        return webcam_config_json

    def webcam_config_by_id(self, webcam_id: str, session_id: str) -> WebcamConfigModel:
        if session_id is None:
            return WebcamConfigModel(webcam_id=webcam_id)
        session_path = get_session_folder_path(session_id)
        camera_name = get_camera_name(webcam_id)
        print(f"webcam id (again): {webcam_id}")
        print(f"camera name: {camera_name}")
        json_file_name = camera_name + "_config.json"
        webcam_config_json_path = Path(session_path) / json_file_name

        try:
            webcam_config_model = WebcamConfigModel.parse_file(webcam_config_json_path)
            logger.info(f"loading webcam_config from: {webcam_config_json_path}")
            return webcam_config_model
        except FileNotFoundError:
            logger.info(
                f"No webcam config file found for this camera, using default camera parameters"
            )
            return WebcamConfigModel(webcam_id=webcam_id)
