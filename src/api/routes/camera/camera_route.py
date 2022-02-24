from fastapi import APIRouter

from src.api.services.user_config import UserConfigService
from src.cameras.cam_singleton import get_or_create_cams
from src.cameras.opencv_camera import WebcamConfig

camera_router = APIRouter()


@camera_router.post("/camera/config")
async def config_cam(webcam_config: WebcamConfig):
    s = UserConfigService()
    s.set_webcam_config(webcam_config)
    return s.webcam_configs


@camera_router.get("/camera/detect")
async def get_cameras():
    return get_or_create_cams()
