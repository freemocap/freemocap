import uuid

import numpy as np
from fastapi import APIRouter
from starlette.requests import Request

from freemocap.prod.cam.detection.cam_singleton import get_or_create_cams

camera_router = APIRouter()


@camera_router.post('/camera/upload')
async def stream_camera_bytes(request: Request):
    body = b''
    with open(f"{uuid.uuid4().hex}.webm", "wb") as fd:
        async for chunk in request.stream():
            body += chunk
            fd.write(chunk)

    # convert into numpy array
    camera_data = np.frombuffer(body, dtype=np.uint8)
    return camera_data


@camera_router.get("/camera/detect")
async def get_cameras():
    return get_or_create_cams()
