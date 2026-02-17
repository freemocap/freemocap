import logging
import multiprocessing
import queue as queue_module
import traceback as traceback_module
from multiprocessing import Queue
from typing import Optional

from pydantic import BaseModel

from ..log_levels import LogLevels
from ..filters.delta_time import DeltaTimeFilter
from ..formatters.custom_formatter import CustomFormatter
from ..log_format_string import LOG_FORMAT_STRING

MIN_LOG_LEVEL_FOR_WEBSOCKET = LogLevels.TRACE.value


class LogRecordModel(BaseModel):
    name: str
    msg: str
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
    exc_info: str | None = None
    exc_text: str | None = None
    stack_info: str | None = None


class WebSocketQueueHandler(logging.Handler):
    """Formats logs and puts them in a queue for websocket distribution.

    Uses non-blocking put: if the queue is full, the log message is
    silently dropped. Blocking the calling thread (which may be a camera
    frame-grab loop) to wait for the websocket relay to drain is never
    acceptable.

    Builds the queue payload from explicit field extraction rather than
    splatting record.__dict__, which avoids pickling failures from
    unpicklable args (cv2.VideoCapture, CameraConfig, etc.), unknown
    fields (taskName on 3.12+), and traceback frame locals.
    """

    def __init__(self, queue: multiprocessing.Queue):
        super().__init__()
        self.queue = queue
        self.addFilter(DeltaTimeFilter())
        self.setFormatter(CustomFormatter(LOG_FORMAT_STRING))

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno < MIN_LOG_LEVEL_FOR_WEBSOCKET:
            return
        try:
            # Format first — populates record.message and record.asctime
            formatted_message = self.format(record)

            # Convert exc_info to string safely
            exc_info_str: str | None = None
            if record.exc_info:
                try:
                    exc_info_str = "".join(
                        traceback_module.format_exception(*record.exc_info)
                    )
                except Exception:
                    exc_info_str = f"{record.exc_info[0].__name__}: {record.exc_info[1]}"

            exc_text_str: str | None = None
            if record.exc_text:
                exc_text_str = str(record.exc_text)

            stack_info_str: str | None = None
            if record.stack_info:
                stack_info_str = str(record.stack_info)

            payload = LogRecordModel(
                name=record.name,
                msg=str(record.msg) if record.msg is not None else "",
                args=[],  # Args are already baked into record.message — no need to pickle them
                levelname=record.levelname,
                levelno=record.levelno,
                pathname=record.pathname,
                filename=record.filename,
                module=record.module,
                lineno=record.lineno,
                funcName=record.funcName,
                created=record.created,
                msecs=record.msecs,
                relativeCreated=record.relativeCreated,
                thread=record.thread or 0,
                threadName=record.threadName or "",
                processName=record.processName or "",
                process=record.process or 0,
                delta_t=getattr(record, "delta_t", "0.000ms"),
                message=record.getMessage(),
                asctime=getattr(record, "asctime", ""),
                formatted_message=formatted_message,
                type="LogRecord",
                exc_info=exc_info_str,
                exc_text=exc_text_str,
                stack_info=stack_info_str,
            ).model_dump()

            self.queue.put_nowait(payload)
        except queue_module.Full:
            pass
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