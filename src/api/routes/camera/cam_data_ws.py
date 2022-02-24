import base64
import json
import logging
import traceback

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket

from src.api.services.board_detect_service import BoardDetectService
from src.api.services.mediapipe_detect_service import MediapipeSkeletonDetectionService

logger = logging.getLogger(__name__)

cam_ws_router = APIRouter()


class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, bytes):
            return str(obj, encoding="utf-8")
        return json.JSONEncoder.default(self, obj)


@cam_ws_router.post("/start_realtime_capture")
async def start_realtime_capture():
    pass


@cam_ws_router.get("/begin_board_detection")
async def begin_board_detection():
    service = BoardDetectService()
    await service.run()


@cam_ws_router.websocket("/ws/board_detection")
async def board_detection_as_ws(web_socket: WebSocket):
    await web_socket.accept()

    async def websocket_send(input_image, webcam_id):
        success, frame = cv2.imencode(".png", input_image)
        if success:
            frame_data = json.dumps(
                {"frame": frame, "webcam_id": webcam_id}, cls=MyEncoder
            )
            await web_socket.send_json(frame_data)

    try:
        await BoardDetectService().run_as_loop(cb=websocket_send)
    except:
        traceback.print_exc()
        return


@cam_ws_router.websocket("/ws/skeleton_detection")
async def skeleton_detection_as_ws(web_socket: WebSocket):
    await web_socket.accept()

    async def websocket_send(input_image, webcam_id):
        success, frame = cv2.imencode(".png", input_image)
        if success:
            await web_socket.send_bytes(base64.b64encode(frame.tobytes()))

    await MediapipeSkeletonDetectionService().run_as_loop(cb=websocket_send)


@cam_ws_router.get("/begin_mediapipe_skeleton_detection")
async def begin_mediapipe_skeleton_detection(model_complexity=2):
    """
    model_complexity can be 1 (faster, less accurate) or 2 (slower, more accurate)
    """
    service = MediapipeSkeletonDetectionService(model_complexity)
    await service.run()
