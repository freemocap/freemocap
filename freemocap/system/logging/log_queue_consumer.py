from __future__ import annotations

import logging
import os
import queue
import threading
from queue import Empty

from skellylogs import LogRecordModel, get_websocket_log_queue
from skellylogs.handlers.websocket_log_queue_handler import (
    MAX_WEBSOCKET_LOG_QUEUE_SIZE,
)

FRONTEND_LOG_QUEUE: queue.Queue[dict] = queue.Queue(
    maxsize=MAX_WEBSOCKET_LOG_QUEUE_SIZE #using the websocket log queue size as a reference for the frontend log queue size instead of making up a harcoded number 
)

_consumer_thread: threading.Thread | None = None
_stop_event = threading.Event()


def _write_worker_record_to_main_file(log_entry: dict) -> None:
    log_model = LogRecordModel.from_dict(log_entry)
    record = log_model.to_log_record()

    root_logger = logging.getLogger()

    for handler in root_logger.handlers:
        if isinstance(handler, logging.FileHandler):
            handler.handle(record)


def _consume_log_queue() -> None:
    logs_queue = get_websocket_log_queue()

    while not _stop_event.is_set():
        try:
            log_entry: dict = logs_queue.get(timeout=0.1)

        except Empty:
            continue

        except (EOFError, OSError):
            continue

        if not isinstance(log_entry, dict):
            continue

        # Main-process records have already passed through the main
        # FileHandler. Worker records have not.
        if log_entry.get("process") != os.getpid():
            _write_worker_record_to_main_file(log_entry)

        # All records are forwarded for display in the frontend.
        try:
            FRONTEND_LOG_QUEUE.put_nowait(log_entry)
        except queue.Full:
            pass


def start_log_queue_consumer() -> None:
    global _consumer_thread

    if _consumer_thread is not None and _consumer_thread.is_alive():
        return

    _stop_event.clear()

    _consumer_thread = threading.Thread(
        target=_consume_log_queue,
        name="LogQueueConsumer",
        daemon=True,
    )
    _consumer_thread.start()


def stop_log_queue_consumer() -> None:
    _stop_event.set()

    if _consumer_thread is not None:
        _consumer_thread.join(timeout=1.0)