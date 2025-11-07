import logging
from logging.config import dictConfig
from multiprocessing import Queue
from typing import Optional

from .filters.delta_time import DeltaTimeFilter
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

    def _configure_root_logger(self):
        root = logging.getLogger()
        root.setLevel(self.level.value)

        # Clear existing handlers
        for handler in root.handlers[:]:
            root.removeHandler(handler)

        # Add new handlers
        root.addHandler(self._build_file_handler())

        if self.queue:
            root.addHandler(self._build_websocket_handler())

        root.addHandler(self._build_console_handler())

    def _build_console_handler(self):
        handler = ColoredConsoleHandler()
        handler.setLevel(self.level.value)
        return handler

    def _build_file_handler(self):
        handler = logging.FileHandler(get_log_file_path(), encoding="utf-8")
        handler.setFormatter(logging.Formatter(LOG_FORMAT_STRING))
        handler.addFilter(DeltaTimeFilter())  # Add this line
        handler.setLevel(LogLevels.TRACE.value)
        return handler

    def _build_websocket_handler(self):
        handler = WebSocketQueueHandler(self.queue)
        handler.setLevel(self.level.value)
        return handler

    def configure(self):
        if len(logging.getLogger().handlers) == 0:
            self._configure_root_logger()
