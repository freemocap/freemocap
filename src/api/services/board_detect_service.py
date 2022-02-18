import asyncio

from aiomultiprocess.core import get_manager

from src.core_processor.board_detection.detect import BoardDetection
from src.core_processor.processor import start_camera_capture


class BoardDetectService:

    async def run(self):
        queue = get_manager().Queue()
        await asyncio.gather(
            # Producer
            start_camera_capture(queue),
            # Consumer
            BoardDetection().create_new_process_for_run(queue)
        )
