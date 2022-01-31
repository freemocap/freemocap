import base64

import cv2
from fastapi import APIRouter, WebSocket

from jon_scratch.opencv_camera import OpenCVCamera

cam_ws_router = APIRouter()


@cam_ws_router.websocket("/ws/{webcam_id}")
async def websocket_endpoint(websocket: WebSocket, webcam_id: str):
    await websocket.accept()
    cam = OpenCVCamera(port_number=webcam_id)
    cam.connect()
    while True:
        success, image, timestamp = cam.get_next_frame()
        if not success:
            continue
        if image is None:
            continue
        success, frame = cv2.imencode('.png', image)
        if not success:
            continue
        await websocket.send_bytes(base64.b64encode(frame.tobytes()))
