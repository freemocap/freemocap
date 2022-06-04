import logging
import traceback
from contextlib import contextmanager
from typing import ContextManager, Dict, List, Optional

from pydantic import BaseModel

from src.api.services.user_config import UserConfigService
from src.cameras.capture.opencv_camera.opencv_camera import OpenCVCamera
from src.cameras.detection.cam_singleton import get_or_create_cams
from src.cameras.persistence.video_writer.video_recorder import VideoRecorder
from src.config.webcam_config import WebcamConfig

logger = logging.getLogger(__name__)


class CamAndWriterResponse(BaseModel):
    cv_camera: OpenCVCamera
    video_recorder: Optional[VideoRecorder]

    class Config:
        arbitrary_types_allowed = True


class OpenCVCameraManager:
    def __init__(self, session_id: str):
        self._session_id = session_id
        self._config_service = UserConfigService()
        self._detected_cams_data = get_or_create_cams()

    @property
    def available_webcam_ids(self):
        return [cam_id.webcam_id for cam_id in get_or_create_cams().cameras_found_list]

    def _create_opencv_cameras(self):
        raw_camera_objects = self._detected_cams_data.cameras_found_list
        open_cv_cameras: List[OpenCVCamera] = []
        for this_raw_cam in raw_camera_objects:
            opencv_cam_obj = self._create_single_opencv_cam(this_raw_cam.webcam_id)
            open_cv_cameras.append(opencv_cam_obj)
        return open_cv_cameras

    def _create_single_opencv_cam(self, webcam_id: str):
        webcam_config_model = self._config_service.webcam_config_by_id(webcam_id, self._session_id)
        single_camera_config = WebcamConfig(webcam_id=webcam_config_model.webcam_id,
                                            exposure=webcam_config_model.exposure,
                                            resolution_width=webcam_config_model.resolution_width,
                                            resolution_height=webcam_config_model.resolution_height, )
        return OpenCVCamera(config=single_camera_config)

    @contextmanager
    def start_capture_session_single_cam(
        self, webcam_id: str
    ) -> ContextManager[CamAndWriterResponse]:
        """
        Context manager for easy start up, usage, and cleanup of camera resources.
        Can capture frames from a single webcam or all webcams detected.
        """
        cv_camera = self._create_single_opencv_cam(webcam_id)
        try:
            self._start_frame_capture_on_cam_id(cv_camera)
            yield CamAndWriterResponse(cv_camera=cv_camera)
            self._stop_frame_capture([cv_camera])
        except:
            logger.error("Printing traceback from starting capture session by cam")
            traceback.print_exc()

    @contextmanager
    def start_capture_session_all_cams(
        self,
    ) -> ContextManager[Dict[str, OpenCVCamera]]:

        open_cv_camera_objects = self._create_opencv_cameras()
        try:
            connected_cameras_dict = {}
            for cv_cam in open_cv_camera_objects:
                connected_cameras_dict[cv_cam.webcam_id_as_str] = cv_cam
                self._start_frame_capture_on_cam_id(cv_cam)
            yield connected_cameras_dict

            self._stop_frame_capture(open_cv_camera_objects)
        except:
            logger.error("Printing traceback from starting capture session by cam")
            traceback.print_exc()

    def _start_frame_capture_on_cam_id(self, opencv_cam: OpenCVCamera):
        opencv_cam.connect()
        opencv_cam.start_frame_capture_thread()

    def _stop_frame_capture(self, opencv_cam_objs: List[OpenCVCamera]):
        for cv_cam in opencv_cam_objs:
            cv_cam.stop_frame_capture()
