import multiprocessing
from typing import List
# from faster_fifo import Queue


class AppQueue:
    _queues = {}

    def __init__(self, manager: multiprocessing.Manager):
        self._manager: multiprocessing.Manager = manager

    def create_all(self, webcam_ids: List[str]):
        for webcam_id in webcam_ids:
            self.create(webcam_id)

    def create(self, webcam_id: str):
        if webcam_id not in self._queues:
            self._queues[webcam_id] = {"queue": self._manager.Queue()}

    def get_by_webcam_id(self, webcam_id: str):
        return self._queues[webcam_id]["queue"]


def create_or_get_queue():
    pass
