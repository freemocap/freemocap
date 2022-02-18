import asyncio

from freemocap.prod.cam.detection.cam_singleton import get_or_create_cams
from src.core_processor.app_events.app_queue import AppQueue
from src.core_processor.board_detection.detect import BoardDetection
from src.core_processor.processor import capture_cam_images_new_process


class BoardDetectService:

    async def run(self):
        cams = get_or_create_cams()
        webcam_ids = [
            rawCam.port_number for rawCam in cams.cams_to_use
        ]
        app_queue = AppQueue()
        app_queue.create_all(webcam_ids)
        queues = app_queue.queues
        await asyncio.gather(
            # Producer
            capture_cam_images_new_process(queues),
            # Consumer
            BoardDetection().create_new_process_for_run(queues)
        )
