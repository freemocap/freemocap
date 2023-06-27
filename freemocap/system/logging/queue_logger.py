
import multiprocessing


class QueueLogger():
    def __init__(self, queue: multiprocessing.Queue):
        self._queue = queue

    def info(self, message: str):
        self._queue.put(message)

    def error(self, message: str):
        self._queue.put(message)
    
    def warning(self, message: str):
        self._queue.put(message)

    def debug(self, message: str):
        self._queue.put(message)

    def critical(self, message: str):
        self._queue.put(message)