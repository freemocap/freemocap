import logging
import multiprocessing


class QueueLogger():
    def __init__(self, queue: multiprocessing.Queue, default_logger: logging.Logger):
        self._queue = queue
        self._logger = default_logger

    def info(self, message: str):
        self._queue.put(message)
        self._logger.info(message)

    def error(self, message: str):
        self._queue.put(message)
        self._logger.error(message)
    
    def warning(self, message: str):
        self._queue.put(message)
        self._logger.warning(message)

    def debug(self, message: str):
        self._queue.put(message)
        self._logger.debug(message)

    def critical(self, message: str):
        self._queue.put(message)
        self._logger.critical(message)
