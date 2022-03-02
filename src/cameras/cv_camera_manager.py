import logging
from contextlib import contextmanager
from typing import List

from src.api.services.user_config import UserConfigService
from src.cameras.cam_singleton import get_or_create_cams
from src.cameras.opencv_camera import OpenCVCamera

logger = logging.getLogger(__name__)

_cv_cams = None


class CVCameraManager:
    def __init__(self):
        self._config_service = UserConfigService()
        self._detected_cams_data = get_or_create_cams()
        global _cv_cams
        if _cv_cams is None:
            logger.info("Creating cams.")
            # we create the _cv_cams once, and reuse it for the lifetime of the session
            _cv_cams = self._create_opencv_cams()
            self._cv_cams = _cv_cams
        else:
            logger.info("Reusing already created resources cam resources.")
            self._cv_cams = _cv_cams

    @property
    def cv_cams(self):
        return self._cv_cams

    def cv_cam_by_id(self, webcam_id: str):
        for cam in self._cv_cams:
            if cam.webcam_id_as_str == str(webcam_id):
                return cam
        return None

    def _create_opencv_cams(self):
        raw_webcam_obj = self._detected_cams_data.cams_to_use
        cv_cams: List[OpenCVCamera] = []
        for webcam in raw_webcam_obj:
            single_config = self._config_service.webcam_config_by_id(webcam.webcam_id)
            # TODO: OBS Studio issue causes us to ignore a specific camera ID for Jon's computer.
            if int(webcam.webcam_id) < 3:
                cv_cams.append(OpenCVCamera(config=single_config))
        return cv_cams

    @contextmanager
    def start_capture_session(self, webcam_id: str = None):
        """
        Context manager for easy start up, usage, and cleanup of camera resources.
        Can capture frames from a single webcam or all webcams detected.
        """
        if webcam_id:
            self.start_frame_capture_on_cam_id(webcam_id)
            yield self.cv_cam_by_id(webcam_id)
        else:
            self.start_frame_capture_all_cams()
            yield self._cv_cams

        logger.debug("Cleaning up capture session")
        self.stop_frame_capture_all_cams()

    def start_frame_capture_all_cams(self):
        for cv_cam in self._cv_cams:
            cv_cam.connect()
            cv_cam.start_frame_capture()

    def start_frame_capture_on_cam_id(self, webcam_id: str):
        filtered_cams = list(
            filter(lambda c: c.webcam_id_as_str == str(webcam_id), self._cv_cams)
        )
        assert (
            len(filtered_cams) == 1
        ), "THe CV Cams list should only have 1 cam per webcam_id"
        cv_cam = filtered_cams[0]
        cv_cam.connect()
        cv_cam.start_frame_capture()

    def stop_frame_capture_all_cams(self):
        for cv_cam in self._cv_cams:
            cv_cam.stop_frame_capture()

    def close_all_cameras(self):
        close_all_cameras(self._cv_cams)


def close_all_cameras(cv_cams: List[OpenCVCamera]):
    for cv_cam in cv_cams:
        cv_cam.close()
