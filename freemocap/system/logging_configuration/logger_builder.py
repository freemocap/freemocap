import logging
from logging.config import dictConfig
from multiprocessing import Queue
from typing import Optional

from .filters.delta_time import DeltaTimeFilter
from .filters.stringify_traceback import StringifyTracebackFilter
from .handlers.colored_console import ColoredConsoleHandler
from .handlers.websocket_log_queue_handler import WebSocketQueueHandler
from .log_format_string import LOG_FORMAT_STRING
from .log_levels import LogLevels
from ..default_paths import get_log_file_path


class LoggerBuilder:

    def __init__(self,
                 level: LogLevels,
                 queue: Optional[Queue]):
        self.level = level
        self.queue = queue
        dictConfig({"version": 1, "disable_existing_loggers": False})

    def _configure_root_logger(self) -> None:
        root = logging.getLogger()
        root.setLevel(self.level.value)
        # Stringify live traceback objects before any handler sees the record,
        # to avoid pickling errors when sending to the frontend
        root.addFilter(StringifyTracebackFilter())

        # Clear existing handlers
        for handler in root.handlers[:]:
            root.removeHandler(handler)

        # Add handlers
        root.addHandler(self._build_file_handler())

        if self.queue:
            root.addHandler(self._build_websocket_handler())

        root.addHandler(self._build_console_handler())

    def _build_console_handler(self) -> logging.Handler:
        handler = ColoredConsoleHandler()
        handler.setLevel(self.level.value)
        return handler

    def _build_file_handler(self) -> logging.Handler:
        handler = logging.FileHandler(get_log_file_path(), encoding="utf-8")
        handler.setFormatter(logging.Formatter(LOG_FORMAT_STRING))
        handler.addFilter(DeltaTimeFilter())
        handler.setLevel(LogLevels.TRACE.value)
        return handler

    def _build_websocket_handler(self) -> logging.Handler:
        handler = WebSocketQueueHandler(self.queue)
        handler.setLevel(self.level.value)
        return handler

    def configure(self) -> None:
        """Configure the root logger, clearing any pre-existing handlers.

        Always runs — if something else added handlers before us (a library
        calling basicConfig, etc.) we replace them with our full handler set
        so the WebSocketQueueHandler is guaranteed to be attached.
        """
        self._configure_root_logger()