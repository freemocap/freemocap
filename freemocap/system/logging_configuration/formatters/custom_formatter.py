import logging
from datetime import datetime


class CustomFormatter(logging.Formatter):
    """Base formatter with microsecond timestamps and structured formatting"""

    def __init__(self, format_string: str):
        super().__init__(fmt=format_string, datefmt="%Y-%m-%dT%H:%M:%S")
        self.format_string = format_string

    def formatTime(self, record: logging.LogRecord, datefmt: str = None) -> str:
        return datetime.fromtimestamp(record.created).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
