from typing import Dict

from singleton_decorator import singleton

from src.cameras.capture.opencv_camera.opencv_camera import WebcamConfig


@singleton
class UserConfigService:
    _webcam_config: Dict[str, WebcamConfig] = {}

    @property
    def webcam_configs(self):
        return self._webcam_config

    def webcam_config_by_id(self, webcam_id: str):
        if webcam_id in self._webcam_config:
            return self._webcam_config[webcam_id]
        else:
            return WebcamConfig(webcam_id=int(webcam_id))

    def set_webcam_config(self, webcam_config: WebcamConfig):
        as_str = str(webcam_config.webcam_id)
        self._webcam_config[as_str] = webcam_config
