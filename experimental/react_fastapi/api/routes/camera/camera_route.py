import logging

import cv2
from fastapi import APIRouter
from pydantic import BaseModel
from src.api.services.user_config import UserConfigService, WebcamConfigModel
from src.cameras.detection.cam_singleton import get_or_create_cams
from src.cameras.multicam_manager.cv_camera_manager import OpenCVCameraManager

camera_router = APIRouter()

logger = logging.getLogger(__name__)


class CameraPreviewModel(BaseModel):
    session_id: str = None


@camera_router.post("/camera/config/{session_id}")
async def config_cam(webcam_config_model: WebcamConfigModel, session_id):
    s = UserConfigService()
    return s.save_webcam_config_to_disk(webcam_config_model, session_id)


@camera_router.post("/camera/show_camera/{webcam_id}")
async def show_camera(
        webcam_id: str, camera_preview_model: CameraPreviewModel = CameraPreviewModel()
):
    cv_cam_manager = OpenCVCameraManager(session_id=camera_preview_model.session_id)
    with cv_cam_manager.start_capture_session_single_cam(
            webcam_id
    ) as connected_camera_and_writer:
        should_continue = True
        this_camera = connected_camera_and_writer.cv_camera
        cv2_window_name = "(ESC to close) PREVIEWING camera_" + webcam_id
        while should_continue:
            if not this_camera.new_frame_ready:
                continue
            cv2.imshow(cv2_window_name, this_camera.latest_frame.image)
            # exit loop when user presses ESC key
            exit_key = cv2.waitKey(1)
            if exit_key == 27:
                logger.info("ESC has been pressed.")
                should_continue = False
                cv2.destroyWindow(cv2_window_name)


@camera_router.post("/camera/show_cameras")
async def cv2_imshow_all_camera(
        camera_preview_model: CameraPreviewModel = CameraPreviewModel(),
):
    cv_cam_manager = OpenCVCameraManager(session_id=camera_preview_model.session_id)
    with cv_cam_manager.start_capture_session_all_cams() as connected_cameras_dict:
        logger.info(f"Available cameras: {connected_cameras_dict}")
        should_continue = True
        while should_continue:
            for this_webcam_id, this_open_cv_camera in connected_cameras_dict.items():
                exit_key = cv2.waitKey(1)
                if exit_key == 27:
                    logger.info("ESC has been pressed.")
                    should_continue = False
                    cv2.destroyWindow(cv2_window_name)
                if not this_open_cv_camera.new_frame_ready:
                    continue
                cv2_window_name = "(ESC to close) PREVIEWING camera_" + this_webcam_id
                cv2.imshow(cv2_window_name, this_open_cv_camera.latest_frame.image)
                exit_key = cv2.waitKey(1)
                if exit_key == 27:
                    logger.info("ESC has been pressed.")
                    should_continue = False
                    cv2.destroyWindow(cv2_window_name)


@camera_router.get("/camera/detect")
async def get_cameras():
    return get_or_create_cams()


@camera_router.get("/camera/redetect")
async def redetect_cameras():
    return get_or_create_cams(always_create=True)
