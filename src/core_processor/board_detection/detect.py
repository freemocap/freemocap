import logging

import cv2
from aiomultiprocess import Process
from aiomultiprocess.types import Queue

from src.core_processor.processor import ImagePayload

logger = logging.getLogger(__name__)


class BoardDetection:

    async def create_new_process_for_run(self, queue: Queue):
        p = Process(target=self.process, args=(queue,))
        p.start()
        await p.join()

    async def process(self, queue: Queue):
        while True:
            try:
                message = queue.get(timeout=1)  # type: ImagePayload
                frames = message.frames
                for f in frames:
                    cv2.imshow(str(f.port_number), f.image)
                    exit_key = cv2.waitKey(1)
                    if exit_key == 27:
                        break
            except Exception as e:
                print(e)
                logger.error(e)
