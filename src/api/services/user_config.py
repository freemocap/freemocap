from typing import Dict

from singleton_decorator import singleton

from src.config.webcam_config import WebcamConfig


@singleton
class UserConfigService:
    _dict_of_webcam_configs: Dict[str, WebcamConfig] = {}

    @property
    def webcam_configs(self):
        return self._dict_of_webcam_configs

    def webcam_config_by_id(self, webcam_id_as_str: str) -> WebcamConfig:
        if webcam_id_as_str in self._dict_of_webcam_configs:
            return self._dict_of_webcam_configs[webcam_id_as_str]
        else:
            return WebcamConfig(webcam_id=int(webcam_id_as_str))

    def set_webcam_config(self, webcam_config: WebcamConfig):
        as_str = str(webcam_config.webcam_id)
        self._dict_of_webcam_configs[as_str] = webcam_config
