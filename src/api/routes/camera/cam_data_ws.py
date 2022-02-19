import logging
from time import perf_counter

import aiomultiprocess
import orjson
from fastapi import APIRouter, WebSocket

from jon_scratch.opencv_camera import OpenCVCamera
from src.api.services.board_detect_service import BoardDetectService
from src.api.services.mediapipe_detect_service import MediapipeSkeletonDetectionService

logger = logging.getLogger(__name__)

cam_ws_router = APIRouter()


@cam_ws_router.post("/start_realtime_capture")
async def start_realtime_capture():
    pass


@cam_ws_router.get("/begin_board_detection")
async def begin_board_detection():
    service = BoardDetectService()
    await service.run()

@cam_ws_router.get("/begin_mediapipe_skeleton_detection")
async def begin_mediapipe_skeleton_detection(model_complexity=2):
    """
    model_complexity can be 1 (faster, less accurate) or 2 (slower, more accurate)
    """
    service = MediapipeSkeletonDetectionService()
    service.model_complexity = model_complexity
    await service.run()


## This is for the frontend - this is for showing cam data to something external. nothing else
@cam_ws_router.websocket("/ws/{webcam_id}")
async def websocket_endpoint(websocket: WebSocket, webcam_id: str):
    await websocket.accept()
    # TODO: Consider Spawning a new Process here - alleviate main thread issues
    # We could spawn a new Process here directly
    cam = OpenCVCamera(port_number=webcam_id)
    cam.connect()
    try:
        while True:
            t1_start = perf_counter()
            success, image, timestamp = cam.get_next_frame()
            if not success:
                continue
            if image is None:
                continue
            # success, frame = cv2.imencode('.png', image)
            if not success:
                continue
            d = {
                "frameData": str(image.tobytes()),
                # "frameData": base64.b64encode(frame.tobytes()),
                "timestamp": timestamp,
            }
            d = orjson.dumps(d)
            await websocket.send_bytes(d)
            t1_stop = perf_counter()
            print("Elapsed time per frame:", t1_stop - t1_start)
    except:
        logger.info(f"Camera {webcam_id} is now closed.")
        cam.close()
