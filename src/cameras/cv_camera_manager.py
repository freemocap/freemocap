import logging
import traceback
from contextlib import contextmanager
from typing import ContextManager, Dict, List

import cv2
from pydantic import BaseModel

from src.api.services.user_config import UserConfigService
from src.cameras.cam_singleton import get_or_create_cams
from src.cameras.dtos.create_writer_options import CreateWriterOptions
from src.cameras.opencv_camera import OpenCVCamera
from src.cameras.video_writer.video_writer import VideoWriter

logger = logging.getLogger(__name__)

_cv_cams = None


class CamAndWriterResponse(BaseModel):
    cv_cam: OpenCVCamera
    writer: VideoWriter

    class Config:
        arbitrary_types_allowed = True


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
    def available_webcam_ids(self):
        return [cv_cam.webcam_id_as_str for cv_cam in self._cv_cams]

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
            cv_cams.append(OpenCVCamera(config=single_config))
        return cv_cams

    @contextmanager
    def start_capture_session_single_cam(
        self, webcam_id: str = None
    ) -> ContextManager[CamAndWriterResponse]:
        """
        Context manager for easy start up, usage, and cleanup of camera resources.
        Can capture frames from a single webcam or all webcams detected.
        """
        try:
            writer = self._start_frame_capture_on_cam_id(webcam_id)
            cv_cam = self.cv_cam_by_id(webcam_id)
            yield CamAndWriterResponse(cv_cam=cv_cam, writer=writer)
            self._stop_frame_capture_all_cams()
        except:
            logger.error("Printing traceback from starting capture session by cam")
            traceback.print_exc()

    @contextmanager
    def start_capture_session_all_cams(
        self,
    ) -> ContextManager[List[CamAndWriterResponse]]:
        try:
            writer_dict = self._start_frame_capture_all_cams()
            responses = [
                CamAndWriterResponse(cv_cam=self.cv_cam_by_id(webcam_id), writer=writer)
                for webcam_id, writer in writer_dict.items()
            ]
            yield responses
            self._stop_frame_capture_all_cams()
        except:
            logger.error("Printing traceback from starting capture session by cam")
            traceback.print_exc()

    def _start_frame_capture_all_cams(self) -> Dict[str, VideoWriter]:
        d = {}
        for cv_cam in self._cv_cams:
            cv_cam.connect()
            cv_cam.start_frame_capture()
            d[cv_cam.webcam_id_as_str] = VideoWriter()

        return d

    def _start_frame_capture_on_cam_id(self, webcam_id: str) -> VideoWriter:
        filtered_cams = list(
            filter(lambda c: c.webcam_id_as_str == str(webcam_id), self._cv_cams)
        )
        assert (
            len(filtered_cams) == 1
        ), "The CV Cams list should only have 1 cam per webcam_id"
        cv_cam = filtered_cams[0]
        cv_cam.connect()
        cv_cam.start_frame_capture()
        return VideoWriter()

    def _stop_frame_capture_all_cams(self):
        for cv_cam in self._cv_cams:
            cv_cam.stop_frame_capture()

    def _close_all_cameras(self):
        for cv_cam in self._cv_cams:
            cv_cam.close()
