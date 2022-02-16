import base64
import logging

import cv2
import orjson
from fastapi import APIRouter, WebSocket

from jon_scratch.opencv_camera import OpenCVCamera

logger = logging.getLogger(__name__)
cam_ws_router = APIRouter()


@cam_ws_router.websocket("/ws/{webcam_id}")
async def websocket_endpoint(websocket: WebSocket, webcam_id: str):
    await websocket.accept()
    # TODO: Consider Spawning a new Process here - alleviate main thread issues
    # We could spawn a new Process here directlu
    cam = OpenCVCamera(port_number=webcam_id)
    cam.connect()

    try:
        while True:
            success, image, timestamp = cam.get_next_frame()
            if not success:
                continue
            if image is None:
                continue
            success, frame = cv2.imencode('.png', image)
            if not success:
                continue
            d = {
                "frameData": str(frame.tobytes()),
                # "frameData": base64.b64encode(frame.tobytes()),
                "timestamp": timestamp,
            }
            d = orjson.dumps(d)
            await websocket.send_bytes(d)
    except:
        logger.info(f"Camera {webcam_id} is now closed.")
        cam.close()
