import logging
import multiprocessing
from logging.handlers import QueueHandler


# class QueueLogger():
#     def __init__(self, queue: multiprocessing.Queue, default_logger: logging.Logger):
#         self._queue = queue
#         self._logger = default_logger

#     def info(self, message: str, exc_info: bool = False):
#         self._queue.put(message)
#         self._logger.info(message, exc_info=exc_info)

#     def error(self, message: str, exc_info: bool = False):
#         self._queue.put(message)
#         self._logger.error(message, exc_info=exc_info)
    
#     def warning(self, message: str, exc_info: bool = False):
#         self._queue.put(message)
#         self._logger.warning(message, exc_info=exc_info)

#     def debug(self, message: str, exc_info: bool = False):
#         self._queue.put(message)
#         self._logger.debug(message, exc_info=exc_info)

#     def critical(self, message: str, exc_info: bool = False):
#         self._queue.put(message)
#         self._logger.critical(message, exc_info=exc_info)

class QueueLogger(QueueHandler):
    def __init__(self, queue):
        super().__init__(queue)

    def enqueue(self, record):
        self.queue.put(record)


