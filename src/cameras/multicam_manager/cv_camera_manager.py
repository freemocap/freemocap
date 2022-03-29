import logging
import traceback
from contextlib import contextmanager
from typing import ContextManager, Dict, List

import numpy as np
from pydantic import BaseModel

from src.api.services.user_config import UserConfigService
from src.cameras.detection.cam_singleton import get_or_create_cams
from src.cameras.capture.opencv_camera.opencv_camera import OpenCVCamera
from src.cameras.persistence.video_writer.video_writer import VideoWriter

logger = logging.getLogger(__name__)

_open_cv_cameras = None


class CamAndWriterResponse(BaseModel):
    cv_cam: OpenCVCamera
    writer: VideoWriter

    class Config:
        arbitrary_types_allowed = True


class OpenCVCameraManager:
    def __init__(self, session_id=str):
        self._session_id = session_id
        self._config_service = UserConfigService()
        self._detected_cams_data = get_or_create_cams()
        global _open_cv_cameras
        if _open_cv_cameras is None:
            logger.info("Creating cams.")
            # we create the _cv_cams /once/, and reuse it for the lifetime of the session
            _open_cv_cameras = self._create_opencv_cameras(calibrate_cameras=True)
            self._open_cv_camera_objects = _open_cv_cameras
            # self._timestamp_logger = TimestampLogger(self.available_webcam_ids, self.camera0_id)
            self._number_of_cameras = len(self._open_cv_camera_objects)
        else:
            logger.info("Reusing already created resources cam resources.")
            self._open_cv_camera_objects = _open_cv_cameras

    @property
    def number_of_cameras(self):
        return self._number_of_cameras

    @property
    def available_webcam_ids(self):
        return [cv_cam.webcam_id_as_str for cv_cam in self._open_cv_camera_objects]

    @property
    def camera0_id(self):
        """ ID of the first camera found. This camera will be used as the reference point for time sync and camera position and rotation"""
        return self.available_webcam_ids[0]

    @property
    def open_cv_cameras(self):
        return self._open_cv_camera_objects

    def new_synchronized_frame_available(self):
        new_frame_bool_list = [cam.new_frame for cam in self._open_cv_camera_objects]
        if all(new_frame_bool_list):
            return True
        return False

    def latest_synchronized_frame(self):
        synchronized_frame_dict = {}
        for this_cam in self._open_cv_camera_objects:
            if not this_cam.new_frame:
                logger.error(f'New frame not available for camera {this_cam.webcam_id_as_str}')
                synchronized_frame_dict[this_cam.webcam_id_as_str] = None
            synchronized_frame_dict[this_cam.webcam_id_as_str] = this_cam.latest_frame
        return synchronized_frame_dict

    def cv_cam_by_id(self, webcam_id: str):
        for cam in self._open_cv_camera_objects:
            if cam.webcam_id_as_str == str(webcam_id):
                return cam
        return None

    def _create_opencv_cameras(self, calibrate_cameras=True):
        raw_camera_objects = self._detected_cams_data.cameras_found_list
        open_cv_cameras: List[OpenCVCamera] = []
        for this_raw_cam in raw_camera_objects:
            single_camera_config = self._config_service.webcam_config_by_id(this_raw_cam.webcam_id)
            this_opencv_camera = OpenCVCamera(config=single_camera_config, session_id=self._session_id)
            open_cv_cameras.append(this_opencv_camera)
        return open_cv_cameras

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
    ) -> ContextManager[Dict[str, CamAndWriterResponse]]:

        try:
            available_cam_and_writer_dict = {}
            writer_dict = self._start_frame_capture_all_cams()
            for webcam_id, writer in writer_dict.items():
                available_cam_and_writer_dict[webcam_id] = CamAndWriterResponse(cv_cam=self.cv_cam_by_id(webcam_id),
                                                                                writer=writer)
            yield available_cam_and_writer_dict
            self._stop_frame_capture_all_cams()
        except:
            logger.error("Printing traceback from starting capture session by cam")
            traceback.print_exc()

    def _start_frame_capture_all_cams(self) -> Dict[str, VideoWriter]:
        d = {}
        for cv_cam in self._open_cv_camera_objects:
            cv_cam.connect()
            d[cv_cam.webcam_id_as_str] = VideoWriter()

        # wait until all cameras are connected before starting frame capture
        for cv_cam in self._open_cv_camera_objects:
            cv_cam.start_frame_capture()

        return d

    def _start_frame_capture_on_cam_id(self, webcam_id: str) -> VideoWriter:
        filtered_cams = list(
            filter(lambda c: c.webcam_id_as_str == str(webcam_id), self._open_cv_camera_objects)
        )
        assert (
                len(filtered_cams) == 1
        ), "The CV Cams list should only have 1 cam per webcam_id"
        cv_cam = filtered_cams[0]
        cv_cam.connect()
        cv_cam.start_frame_capture()
        return VideoWriter()

    def _stop_frame_capture_all_cams(self):
        for cv_cam in self._open_cv_camera_objects:
            cv_cam.stop_frame_capture()

    def _close_all_cameras(self):
        for cv_cam in self._open_cv_camera_objects:
            cv_cam.close()
