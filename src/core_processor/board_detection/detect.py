import logging
from time import perf_counter

from orjson import orjson

logger = logging.getLogger(__name__)


class BoardDetection:
    async def process(self, queue):
        while True:
            try:
                t1_start = perf_counter()
                message = queue.get(timeout=.01)
                message = orjson.loads(message)
                t1_stop = perf_counter()
                logger.info(t1_stop - t1_start)
            except:
                pass

