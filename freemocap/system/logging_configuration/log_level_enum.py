import logging
from enum import Enum


class LogLevels(Enum):
    ALL = logging.NOTSET  # 0 # All logs, including those from third-party libraries
    LOOP = 4  # For logs that are printed in a loop
    TRACE = 5  # Low level logs for deep debugging
    DEBUG = logging.DEBUG  # 10 # Detailed information for devs and curious folk
    INFO = logging.INFO  # 20 # General information about the program
    SUCCESS = logging.INFO + 2  # 22 # OMG, something worked!
    API = logging.INFO + 5  # 25 # API calls/responses
    WARNING = logging.WARNING  # 30 # Something unexpected happened, but it's necessarily an error
    ERROR = logging.ERROR  # 40 # Something went wrong!
