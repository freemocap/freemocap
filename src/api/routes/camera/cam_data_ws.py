import logging

import cv2
from fastapi import APIRouter, WebSocket

from src.cameras.capture.dataclasses.frame_payload import FramePayload

logger = logging.getLogger(__name__)

cam_ws_router = APIRouter()


async def websocket_send(web_socket: WebSocket, input_payload: FramePayload):
    if not input_payload.success:
        return
    success, frame = cv2.imencode(".png", input_payload.image)
    if not success:
        return
    await web_socket.send_bytes(frame.tobytes())


@cam_ws_router.websocket("/ws/hello_world")
async def preview_webcam(web_socket: WebSocket):
    await web_socket.accept()
    try:
        await web_socket.send_json({"message": "Hi Nikki"})
    except:
        web_socket.close()
