import logging
from time import perf_counter

from aiomultiprocess import Process
from orjson import orjson

logger = logging.getLogger(__name__)


class BoardDetection:

    async def create_new_process_for_run(self, queue):
        p = Process(target=self.process, args=(queue, ))
        p.start()
        await p.join()

    async def process(self, queue):
        while True:
            try:
                message = queue.get(timeout=.01)
                frameData = orjson.loads(message)
                # frameData["image"]
                # frameData["timestamp"]
                # Do your thing
            except:
                pass

