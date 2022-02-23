from fastapi import APIRouter

from src.cameras.cam_singleton import get_or_create_cams

camera_router = APIRouter()


@camera_router.post("/camera/config/{webcam_id}")
async def config_cam(webcam_id: str):
    pass


@camera_router.get("/camera/detect")
async def get_cameras():
    return get_or_create_cams()
