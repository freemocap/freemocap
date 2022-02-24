from typing import List

from src.api.services.user_config import UserConfigService
from src.cameras.cam_singleton import get_or_create_cams
from src.cameras.opencv_camera import OpenCVCamera


def create_opencv_cams():
    config_service = UserConfigService()
    cams = get_or_create_cams()
    raw_webcam_obj = cams.cams_to_use
    cv_cams: List[OpenCVCamera] = []
    for webcam in raw_webcam_obj:
        single_config = config_service.webcam_config_by_id(webcam.webcam_id)
        # TODO: OBS Studio issue causes us to ignore a specific camera ID for Jon's computer.
        if int(webcam.webcam_id) < 3:
            cv_cams.append(OpenCVCamera(config=single_config))

    for cv_cam in cv_cams:
        cv_cam.connect()

    return cv_cams


def close_all_cameras(cv_cams: List[OpenCVCamera]):
    for cv_cam in cv_cams:
        cv_cam.close()
