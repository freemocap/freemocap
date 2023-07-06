import multiprocessing
from logging.handlers import QueueHandler

class QueueLogger(QueueHandler):
    def __init__(self, queue: multiprocessing.Queue):
        super().__init__(queue)

    def enqueue(self, record):
        self.queue.put(record)


