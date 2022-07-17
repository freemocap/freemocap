from typing import List

from pydantic import BaseModel

from src.config.home_dir import os_independent_home_dir


class WebcamConfig(BaseModel):
    webcam_id: int = 0
    exposure: int = -6
    resolution_width: int = 1280
    resolution_height: int = 720
    save_video: bool = False
    # fourcc: str = "MP4V"
    fourcc: str = "MJPG"
    base_save_video_dir = os_independent_home_dir()


def webcam_config_to_qt_parameter_list(
    webcam_config: WebcamConfig = WebcamConfig(),
) -> List:
    """
    take in a webcam_config and return a parameter_tree_group that you can feed into a pyqtgraph Parameter tree like this:

    ```python
    parameter_tree = ParameterTree()
    parameters_group = Parameter.create(name='Available Webcams', type='group',
                                            children=webcam_config_to_qt_parameter_group(WebcamConfig())
    parameter_tree.setParameters(parameters_group)
    ```
    """
    this_webcam_id = webcam_config.webcam_id
    parameter_list = [
        {"name": "use this camera❓", "type": "bool", "value": True},
        {"name": "exposure", "type": "int", "value": webcam_config.exposure},
        {
            "name": "resolution_width",
            "type": "int",
            "value": webcam_config.resolution_width,
        },
        {
            "name": "resolution_height",
            "type": "int",
            "value": webcam_config.resolution_height,
        },
    ]

    return parameter_list
