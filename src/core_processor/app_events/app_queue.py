import multiprocessing
from multiprocessing import Queue
from typing import Dict, List, Optional

from aiomultiprocess.core import get_manager


class CameraFrameQueue:
    webcam_id: str
    queue: Optional[Queue]

    def __init__(self, webcam_id: str, queue: Queue):
        self.webcam_id = webcam_id
        self.queue = queue


class AppQueue:
    _queues: Dict[str, CameraFrameQueue] = {}

    def __init__(self, manager: multiprocessing.Manager = None):
        if not manager:
            manager = get_manager()
        self._manager: multiprocessing.Manager = manager

    def create_all(self, webcam_ids: List[str]):
        for webcam_id in webcam_ids:
            self.create(webcam_id)

    def create(self, webcam_id: str):
        if webcam_id not in self._queues:
            self._queues[webcam_id] = CameraFrameQueue(
                webcam_id=webcam_id,
                queue=self._manager.Queue()
            )

    def get_by_webcam_id(self, webcam_id: str):
        return self._queues[webcam_id].queue

    @property
    def queues(self):
        return self._queues

def create_or_get_queue():
    pass
