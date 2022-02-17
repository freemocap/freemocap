import logging

from src.core_processor.app_events.app_queue import AppQueue
from src.core_processor.subscribers.subscribers import subscribers

logger = logging.getLogger(__name__)


class EventNotifier:

    def __init__(self, webcam_ids):
        self._app_queues = AppQueue()
        self._workers = []
        self._webcam_ids = webcam_ids
        self._construct()

    def _construct(self):
        self._workers = [sub() for sub in subscribers]

    async def notify_all_subscribers(self):
        while True:
            for webcam_id in self._webcam_ids:
                queue = self._app_queues.get_by_webcam_id(webcam_id)
                try:
                    message = await queue.get()
                    for worker in self._workers:
                        await worker.process(message)
                except Exception as e:
                    logger.error(e)
                    logger.error("Notifier dead")
