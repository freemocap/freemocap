import asyncio

from aiomultiprocess.core import get_manager

from src.core_processor.board_detection.detect import BoardDetection
from src.core_processor.mediapipe_skeleton_detection.detect import MediapipeSkeletonDetection
from src.core_processor.processor import start_camera_capture


class MediapipeSkeletonDetectionService:
    model_complexity: int=1

    async def run(self):
        queue = get_manager().Queue()
        await asyncio.gather(
            # Producer
            start_camera_capture(queue),
            # Consumer
            MediapipeSkeletonDetection().create_new_process_for_run(queue)
        )
