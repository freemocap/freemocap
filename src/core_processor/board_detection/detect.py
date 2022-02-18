import logging

import cv2
from aiomultiprocess import Process

logger = logging.getLogger(__name__)


class BoardDetection:

    async def create_new_process_for_run(self, queue):
        p = Process(target=self.process, args=(queue,))
        p.start()
        await p.join()

    async def process(self, queue):
        while True:
            try:
                image, timestamp = queue.get(timeout=.01)
                cv2.imshow('blah', image)
                exit_key = cv2.waitKey(1)
                if exit_key == 27:
                    break
            except:
                pass
