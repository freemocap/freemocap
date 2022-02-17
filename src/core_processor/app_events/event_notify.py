import asyncio
import logging
import multiprocessing

from src.core_processor.subscribers.subscribers import subscribers

logger = logging.getLogger(__name__)


class EventNotifier:

    def __init__(self, webcam_ids):
        self._workers = self._construct()
        self._webcam_ids = webcam_ids

    async def notify_all_subscribers(self, queue: multiprocessing.Queue):
        while True:
            try:
                message = queue.get(timeout=1)
                for worker in self._workers:
                    await worker.process(message)
            except Exception as e:
                print(e)
                logger.error("Notifier dead")

    def _construct(self):
        return [sub() for sub in subscribers]
