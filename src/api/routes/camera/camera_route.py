import logging
import traceback

import cv2
from fastapi import APIRouter
from pydantic import BaseModel

from src.api.services.user_config import UserConfigService, WebcamConfigModel
from src.cameras.capture.opencv_camera.opencv_camera import OpenCVCamera
from src.cameras.detection.cam_singleton import get_or_create_cams
from src.cameras.multicam_manager.cv_camera_manager import OpenCVCameraManager

camera_router = APIRouter()

logger = logging.getLogger(__name__)


class CameraPreviewModel(BaseModel):
    session_id: str

@camera_router.post("/camera/config")
async def config_cam(webcam_config_model: WebcamConfigModel):
    s = UserConfigService()
    return s.save_webcam_config_to_disk(webcam_config_model, session_id)


@camera_router.post("/camera/cv2_imshow_one_camera/{webcam_id}")
async def cv2_imshow_one_camera(webcam_id: str, camera_preview_model: CameraPreviewModel):
    with OpenCVCameraManager(session_id=camera_preview_model.session_id).start_capture_session_single_cam() as connected_camera_and_writer:
        should_continue = True
        this_camera = connected_camera_and_writer.cv_camera
        while should_continue:
            if not this_camera.new_frame_ready:
                continue
            cv2.imshow('(ESC to close) PREVIEWING camera_' + webcam_id, this_camera.latest_frame.image)
            # exit loop when user presses ESC key
            exit_key = cv2.waitKey(1)
            if exit_key == 27:
                logger.info("ESC has been pressed.")
                should_continue = False


@camera_router.post("/camera/cv2_imshow_all_cameras")
async def cv2_imshow_all_camera():
    with OpenCVCameraManager().start_capture_session_all_cams() as connected_cameras_dict:
        should_continue = True
        while should_continue:
            for this_webcam_id, this_open_cv_camera in connected_cameras_dict.items():
                if not this_open_cv_camera.new_frame_ready:
                    continue
                cv2.imshow('(ESC to close) PREVIEWING camera_' + this_webcam_id, this_open_cv_camera.latest_frame.image)
                # exit loop when user presses ESC key
            exit_key = cv2.waitKey(1)
            if exit_key == 27:
                logger.info("ESC has been pressed.")
                should_continue = False


@camera_router.get("/camera/detect")
async def get_cameras():
    return get_or_create_cams()


@camera_router.get("/camera/redetect")
async def redetect_cameras():
    return get_or_create_cams(always_create=True)

