import logging
import logging.handlers
import sys
from logging.config import dictConfig
from freemocap.system.logging.log_handler import LogHandler

from freemocap.system.paths_and_files_names import get_log_file_path

DEFAULT_LOGGING = {"version": 1, "disable_existing_loggers": False}

LOG_FILE_PATH = None

format_string = "[%(asctime)s.%(msecs)04d] [%(levelname)8s] [%(name)s] [%(funcName)s():%(lineno)s] [PID:%(process)d TID:%(thread)d] %(message)s"

default_logging_formatter = logging.Formatter(fmt=format_string, datefmt="%Y-%m-%d %H:%M:%S")


def get_logging_handlers():
    dictConfig(DEFAULT_LOGGING)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(default_logging_formatter)

    # Setup File handler (from https://stackoverflow.com/a/24507130/14662833 )

    file_handler = logging.FileHandler(get_log_file_path())
    file_handler.setFormatter(default_logging_formatter)
    file_handler.setLevel(logging.DEBUG)

    log_handler = LogHandler()
    log_handler.setFormatter(default_logging_formatter)

    return [console_handler, file_handler, log_handler]


# def configure_logging():
#     print(f"Setting up freemocap logging  {__file__}")

#     if len(logging.getLogger().handlers) == 0:
#         handlers = get_logging_handlers()
#         for handler in handlers:
#             if not handler in logging.getLogger("").handlers:
#                 logging.getLogger("").handlers.append(handler)
            
#             if isinstance(handler, LogHandler):
#                 logging.getLogger().addHandler(handler)

#         logging.root.setLevel(logging.DEBUG)
#     else:
#         logger = logging.getLogger(__name__)
#         logger.info("Logging already configured")

def configure_logging():
    print(f"Setting up freemocap logging  {__file__}")

    # Clear existing handlers
    logging.getLogger().handlers = []

    # Configure custom handlers
    handlers = get_logging_handlers()
    log_handler = None
    for handler in handlers:
        if not handler in logging.getLogger("").handlers:
            logging.getLogger("").handlers.append(handler)

        if isinstance(handler, LogHandler):
            log_handler = handler

    logging.root.setLevel(logging.DEBUG)

    logger = logging.getLogger(__name__)
    logger.info("Logging configured")

    return log_handler
