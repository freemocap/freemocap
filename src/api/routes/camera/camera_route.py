from fastapi import APIRouter

from src.api.services.user_config import UserConfigService, WebcamConfigModel
from src.cameras.detection.cam_singleton import get_or_create_cams

camera_router = APIRouter()


@camera_router.post("/camera/config")
async def config_cam(webcam_config_model: WebcamConfigModel):
    s = UserConfigService()
    return s.save_webcam_config_to_disk(webcam_config_model)


@camera_router.get("/camera/detect")
async def get_cameras():
    return get_or_create_cams()


@camera_router.get("/camera/redetect")
async def redetect_cameras():
    return get_or_create_cams(always_create=True)
