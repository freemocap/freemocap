import logging
import traceback

import cv2
from fastapi import APIRouter, WebSocket

from src.api.services.board_detect_service import BoardDetectService
from src.api.services.mediapipe_detect_service import MediapipeSkeletonDetectionService
from src.cameras.cv_camera_manager import CVCameraManager

logger = logging.getLogger(__name__)

cam_ws_router = APIRouter()


@cam_ws_router.get("/begin_board_detection")
async def begin_board_detection():
    service = BoardDetectService()
    await service.run()


@cam_ws_router.websocket("/ws/board_detection/{webcam_id}")
async def board_detection_as_ws(web_socket: WebSocket, webcam_id: str):
    await web_socket.accept()

    async def websocket_send(input_image):
        success, frame = cv2.imencode(".png", input_image)
        if success:
            await web_socket.send_bytes(frame.tobytes())

    try:
        await BoardDetectService().run_detection_on_cam_id(
            webcam_id=webcam_id, cb=websocket_send
        )
    except:
        logger.error("Websocket ended")
        traceback.print_exc()
        return


@cam_ws_router.websocket("/ws/skeleton_detection/{webcam_id}")
async def skeleton_detection_as_ws(
    web_socket: WebSocket, webcam_id: str, model_complexity: int
):
    await web_socket.accept()

    async def websocket_send(input_image):
        success, frame = cv2.imencode(".png", input_image)
        if success:
            await web_socket.send_bytes(frame.tobytes())

    try:
        await MediapipeSkeletonDetectionService(CVCameraManager()).run_as_loop(
            webcam_id=webcam_id, cb=websocket_send, model_complexity=model_complexity
        )
    except:
        logger.error("Websocket ended")
        traceback.print_exc()
        return


@cam_ws_router.get("/begin_mediapipe_skeleton_detection")
async def begin_mediapipe_skeleton_detection(model_complexity: int):
    """
    model_complexity can be 1 (faster, less accurate) or 2 (slower, more accurate)
    """
    service = MediapipeSkeletonDetectionService(CVCameraManager())
    service.run(model_complexity)
