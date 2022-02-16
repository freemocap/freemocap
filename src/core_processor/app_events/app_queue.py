import asyncio
from asyncio import Queue

from singleton_decorator import singleton


@singleton
class AppQueue:
    _queues = {
        "0": {
            "queue": Queue()
        }
    }

    def create(self, webcam_id):
        if webcam_id not in self._queues:
            self._queues[webcam_id] = {"queue": Queue()}

    def get_by_webcam_id(self, webcam_id: str) -> asyncio.Queue:
        return self._queues[webcam_id]["queue"]


def create_or_get_queue():
    pass
