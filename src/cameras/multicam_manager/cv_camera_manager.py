import logging
import traceback
from contextlib import contextmanager
from typing import ContextManager, Dict, List

import numpy as np
from pydantic import BaseModel

from src.api.services.user_config import UserConfigService
from src.cameras.detection.cam_singleton import get_or_create_cams
from src.cameras.capture.opencv_camera.opencv_camera import OpenCVCamera
from src.cameras.persistence.video_writer.video_recorder import VideoRecorder
from src.config.webcam_config import WebcamConfig

logger = logging.getLogger(__name__)

_open_cv_cameras = None


class CamAndWriterResponse(BaseModel):
    cv_camera: OpenCVCamera
    video_recorder: VideoRecorder

    class Config:
        arbitrary_types_allowed = True


class OpenCVCameraManager:
    def __init__(self, session_id: str):
        self._session_id = session_id
        self._config_service = UserConfigService()
        self._detected_cams_data = get_or_create_cams()
        global _open_cv_cameras
        if _open_cv_cameras is None:
            logger.info("Creating cams.")
            # we create the _cv_cams /once/, and reuse it for the lifetime of the session
            _open_cv_cameras = self._create_opencv_cameras()
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

    @property
    def new_synchronized_frame_available(self):
        new_frame_bool_list = [cam.new_frame_ready for cam in self._open_cv_camera_objects]
        if all(new_frame_bool_list):
            return True
        return False

    def latest_synchronized_frame(self):
        synchronized_frame_dict = {}
        for this_cam in self._open_cv_camera_objects:

            if not self.new_synchronized_frame_available:
                logger.error(f'New frame not available for camera {this_cam.webcam_id_as_str}')
                synchronized_frame_dict[this_cam.webcam_id_as_str] = None

            synchronized_frame_dict[this_cam.webcam_id_as_str] = this_cam.latest_frame
        return synchronized_frame_dict

    def cv_cam_by_id(self, webcam_id: str):
        for cam in self._open_cv_camera_objects:
            if cam.webcam_id_as_str == str(webcam_id):
                return cam
        return None

    def _create_opencv_cameras(self):
        raw_camera_objects = self._detected_cams_data.cameras_found_list
        open_cv_cameras: List[OpenCVCamera] = []
        for this_raw_cam in raw_camera_objects:
            webcam_config_model = self._config_service.webcam_config_by_id(this_raw_cam.webcam_id, self._session_id)
            single_camera_config = WebcamConfig(webcam_id=webcam_config_model.webcam_id,
                                                exposure=webcam_config_model.exposure,
                                                resolution_width=webcam_config_model.resolution_width,
                                                resolution_height=webcam_config_model.resolution_height, )
            this_opencv_camera = OpenCVCamera(config=single_camera_config)
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
            video_recorder = self._start_frame_capture_on_cam_id(webcam_id)
            cv_camera = self.cv_cam_by_id(webcam_id)
            yield CamAndWriterResponse(cv_camera=cv_camera, video_recorder=video_recorder)
            self._stop_frame_capture_all_cams()
        except:
            logger.error("Printing traceback from starting capture session by cam")
            traceback.print_exc()

    @contextmanager
    def start_capture_session_all_cams(
            self,
    ) -> ContextManager[Dict[str, OpenCVCamera]]:

        try:
            connected_cameras_dict = {}
            for cv_cam in self._open_cv_camera_objects:
                connected_cameras_dict[cv_cam.webcam_id_as_str] = cv_cam
                cv_cam.connect()
                cv_cam.start_frame_capture_thread()
            yield connected_cameras_dict

            self._stop_frame_capture_all_cams()
        except:
            logger.error("Printing traceback from starting capture session by cam")
            traceback.print_exc()

    def _start_frame_capture_on_cam_id(self, webcam_id: str):
        filtered_cams = list(
            filter(lambda c: c.webcam_id_as_str == str(webcam_id), self._open_cv_camera_objects)
        )
        assert (
                len(filtered_cams) == 1
        ), "The CV Cams list should only have 1 cam per webcam_id"
        cv_cam = filtered_cams[0]
        cv_cam.connect()
        cv_cam.start_frame_capture_thread()

    def _stop_frame_capture_all_cams(self):
        for cv_cam in self._open_cv_camera_objects:
            cv_cam.stop_frame_capture()

    def _close_all_cameras(self):
        for cv_cam in self._open_cv_camera_objects:
            cv_cam.close()
