import logging
import traceback

import cv2
from fastapi import APIRouter, WebSocket

from src.cameras.capture.dataclasses.frame_payload import FramePayload
from src.cameras.capture.opencv_camera.opencv_camera import OpenCVCamera
from src.config.webcam_config import WebcamConfig

logger = logging.getLogger(__name__)

cam_ws_router = APIRouter()


async def websocket_send(web_socket: WebSocket, input_payload: FramePayload):
    if not input_payload.success:
        return
    success, frame = cv2.imencode(".png", input_payload.image)
    if not success:
        return
    await web_socket.send_bytes(frame.tobytes())


@cam_ws_router.websocket("/ws/preview/{webcam_id}")
async def preview_webcam(web_socket: WebSocket, webcam_id: str):
    await web_socket.accept()
    try:
        cv_cam = OpenCVCamera(
            WebcamConfig(webcam_id=webcam_id),
        )
        connected = cv_cam.connect()
        if not connected:
            return
        cv_cam.start_frame_capture_thread()

        # TODO: Allow connections to drop, allow signals to get through so we can cancel
        while cv_cam.is_capturing_frames:
            if cv_cam.new_frame_ready:
                await websocket_send(web_socket, cv_cam.latest_frame)
    except:
        logger.error("Websocket ended")
        traceback.print_exc()
        return
    finally:
        await web_socket.close()



