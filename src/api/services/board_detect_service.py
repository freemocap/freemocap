import asyncio

from aiomultiprocess.core import get_manager

from src.core_processor.board_detection.detect import BoardDetection
from src.core_processor.processor import capture_cam_images_new_process


class BoardDetectService:

    async def run(self):
        manager = get_manager()
        queue = manager.Queue()

        await asyncio.gather(
            # Producer
            capture_cam_images_new_process(queue),
            # Consumer
            BoardDetection().create_new_process_for_run(queue)
        )

