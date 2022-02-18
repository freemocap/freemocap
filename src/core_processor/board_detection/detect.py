import logging
from typing import Dict

import cv2
from aiomultiprocess import Process

from src.core_processor.app_events.app_queue import CameraFrameQueue

logger = logging.getLogger(__name__)


class BoardDetection:

    async def create_new_process_for_run(self, queues: Dict[str, CameraFrameQueue]):
        p = Process(target=self.process, args=(queues,))
        p.start()
        await p.join()

    async def process(self, queues: Dict[str, CameraFrameQueue]):
        while True:
            for webcam_id in queues:
                queue = queues[webcam_id].queue
                try:
                    image, timestamp = queue.get(timeout=.01)
                    cv2.imshow(webcam_id, image)
                    exit_key = cv2.waitKey(1)
                    if exit_key == 27:
                        break
                except:
                    pass
