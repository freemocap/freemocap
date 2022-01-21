from fastapi import APIRouter
from freemocap.prod.cam.cam_detection import DetectPossibleCameras

# Make a router
camera_router = APIRouter()


# create an endpoint
@camera_router.get("/camera/detect")
def camera_detect():
    dpc = DetectPossibleCameras()
    return dpc.find_available_cameras()
