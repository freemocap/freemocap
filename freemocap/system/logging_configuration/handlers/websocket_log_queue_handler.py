import logging
import multiprocessing
from multiprocessing import Queue
from typing import Optional

from pydantic import BaseModel

from freemocap.system.logging_configuration.log_levels import LogLevels
from ..filters.delta_time import DeltaTimeFilter
from ..formatters.custom_formatter import CustomFormatter
from ..log_format_string import LOG_FORMAT_STRING



class LogRecordModel(BaseModel):
    name: str
    msg: str|None = None
    args: list
    levelname: str
    levelno: int
    pathname: str
    filename: str
    module: str
    exc_info: str|None
    exc_text: str|None
    stack_info: str|None
    lineno: int
    funcName: str
    created: float
    msecs: float
    relativeCreated: float
    thread: int
    threadName: str
    processName: str
    process: int
    delta_t: str
    message: str
    asctime: str
    formatted_message: str
    type: str
    message_type: str = "log_record"

class WebSocketQueueHandler(logging.Handler):
    """Formats logs and puts them in a queue for websocket distribution"""

    def __init__(self, queue: multiprocessing.Queue):
        super().__init__()
        self.queue = queue
        self.addFilter(DeltaTimeFilter())
        self.setFormatter(CustomFormatter(LOG_FORMAT_STRING))

    def emit(self, record: logging.LogRecord):
        if record.levelno > LogLevels.INFO.value:
            log_record_dict =  record.__dict__
            log_record_dict["formatted_message"] = self.format(record)
            log_record_dict['type'] = record.__class__.__name__
            log_record_dict['exc_info'] = str(log_record_dict['exc_info']) if log_record_dict['exc_info'] else None
            if not isinstance(log_record_dict['msg'], str):
                log_record_dict['msg'] = str(log_record_dict['msg'])
            self.queue.put(LogRecordModel(**log_record_dict).model_dump())


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