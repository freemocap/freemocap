import logging
import multiprocessing
from logging.handlers import QueueHandler
from multiprocessing import Queue
from typing import Optional

from skellycam.system.logging_configuration.log_levels import LogLevels

from ..filters.delta_time import DeltaTimeFilter
from ..formatters.custom_formatter import CustomFormatter
from ..log_format_string import LOG_FORMAT_STRING

MIN_LOG_LEVEL_FOR_WEBSOCKET = LogLevels.TRACE.value


class WebSocketQueueHandler(QueueHandler):
    """Formats logs and puts them in a queue for websocket distribution"""

    def __init__(self, queue: multiprocessing.Queue):
        super().__init__()
        self.queue = queue
        self.addFilter(DeltaTimeFilter())
        self.setFormatter(CustomFormatter(LOG_FORMAT_STRING))


    def emit(self, record: logging.LogRecord):
        if record.levelno > MIN_LOG_LEVEL_FOR_WEBSOCKET:
            try:
                # Prepare the record for pickling (handles exception info)
                prepared_record = self.prepare(record)
                self.queue.put(prepared_record)
            except Exception:
                self.handleError(record)

MAX_WEBSOCKET_LOG_QUEUE_SIZE = 1000
WEBSOCKET_LOG_QUEUE: Optional[Queue] = None
def create_websocket_log_queue() -> Queue:
    global WEBSOCKET_LOG_QUEUE
    if WEBSOCKET_LOG_QUEUE is None:
        WEBSOCKET_LOG_QUEUE = Queue(maxsize=MAX_WEBSOCKET_LOG_QUEUE_SIZE)
    return WEBSOCKET_LOG_QUEUE

def get_websocket_log_queue() -> Queue:
    global WEBSOCKET_LOG_QUEUE
    if WEBSOCKET_LOG_QUEUE is None:
        raise ValueError("Websocket log queue not created yet")
    return WEBSOCKET_LOG_QUEUE