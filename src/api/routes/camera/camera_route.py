import random
import uuid

import numpy as np
from fastapi import APIRouter
from starlette.requests import Request

camera_router = APIRouter()


# create an endpoint
# @camera_router.post("/camera")
# def begin_detection():
#     pass


@camera_router.post('/camera/upload')
async def stream_camera_bytes(request: Request):
    body = b''
    # uuid_str = str(uuid.uuid4())
    with open(f"{random.randint(0,10000)}.webm", "wb") as fd:
        async for chunk in request.stream():
            body += chunk
            fd.write(chunk)

    # convert into numpy array
    camera_data = np.frombuffer(body, dtype=np.uint8)
    print(camera_data)
