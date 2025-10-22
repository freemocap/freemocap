import logging
import multiprocessing
from multiprocessing import Queue
from typing import Optional

from pydantic import BaseModel

from skellycam.system.logging_configuration.log_levels import LogLevels
from ..filters.delta_time import DeltaTimeFilter
from ..formatters.custom_formatter import CustomFormatter
from ..log_format_string import LOG_FORMAT_STRING

MIN_LOG_LEVEL_FOR_WEBSOCKET = LogLevels.TRACE.value

class LogRecordModel(BaseModel):
    name: str

    args: list
    levelname: str
    levelno: int
    pathname: str
    filename: str
    module: str
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
    msg: str|None = None
    exc_info: str|tuple|None = None
    exc_text: str|None = None
    stack_info: str|None = None

class WebSocketQueueHandler(logging.Handler):
    """Formats logs and puts them in a queue for websocket distribution"""

    def __init__(self, queue: multiprocessing.Queue):
        super().__init__()
        self.queue = queue
        self.addFilter(DeltaTimeFilter())
        self.setFormatter(CustomFormatter(LOG_FORMAT_STRING))


    def emit(self, record: logging.LogRecord):
        if record.levelno > MIN_LOG_LEVEL_FOR_WEBSOCKET:
            log_record_dict = record.__dict__
            
            # Preserve original message formatting
            formatted_message = self.format(record)
            log_record_dict["formatted_message"] = formatted_message
            
            # Ensure proper string conversion while preserving whitespace
            if not isinstance(log_record_dict['msg'], str):
                log_record_dict['msg'] = str(log_record_dict['msg'])
            
            log_record_dict['type'] = record.__class__.__name__
            # Convert exc_info tuple to string to make it picklable
            if log_record_dict.get('exc_info'):
                if isinstance(log_record_dict['exc_info'], tuple):
                    # Format the exception info as a string
                    log_record_dict['exc_info'] = self.formatter.formatException(
                        ei=log_record_dict['exc_info']
                    )
                elif not isinstance(log_record_dict['exc_info'], str):
                    # If it's not a tuple or string, set to None
                    log_record_dict['exc_info'] = None

            # Also handle exc_text if present
            if log_record_dict.get('exc_text') and not isinstance(log_record_dict['exc_text'], str):
                log_record_dict['exc_text'] = str(log_record_dict['exc_text'])

            # Handle stack_info if present
            if log_record_dict.get('stack_info') and not isinstance(log_record_dict['stack_info'], str):
                log_record_dict['stack_info'] = str(log_record_dict['stack_info'])
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