import logging
import logging.handlers
import sys
from logging.config import dictConfig

from freemocap.system.paths_and_filenames.path_getters import get_log_file_path

DEFAULT_LOGGING = {"version": 1, "disable_existing_loggers": False}

LOG_FILE_PATH = None

format_string = "[%(asctime)s.%(msecs)04d] [%(levelname)8s] [%(name)s] [%(funcName)s():%(lineno)s] [PID:%(process)d TID:%(thread)d] %(message)s"

default_logging_formatter = logging.Formatter(fmt=format_string, datefmt="%Y-%m-%d %H:%M:%S")

log_view_logging_format_string = "[%(asctime)s.%(msecs)04d] [%(levelname)4s] [%(name)s] [Process:%(process)d Thread:%(thread)d] ::::: [%(name)s:%(funcName)s():%(lineno)s] |||| %(message)s."

# logging.basicConfig(level=logging.WARNING)


def get_logging_handlers():
    dictConfig(DEFAULT_LOGGING)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(default_logging_formatter)

    # Setup File handler (from https://stackoverflow.com/a/24507130/14662833 )

    file_handler = logging.FileHandler(get_log_file_path(), encoding="utf-8")
    file_handler.setFormatter(default_logging_formatter)
    file_handler.setLevel(logging.DEBUG)

    return [console_handler, file_handler]


def configure_logging():
    print(f"Setting up freemocap logging  {__file__}")

    if len(logging.getLogger().handlers) == 0:
        handlers = get_logging_handlers()
        for handler in handlers:
            if handler not in logging.getLogger("").handlers:
                logging.getLogger("").handlers.append(handler)

        logging.root.setLevel(logging.DEBUG)
    else:
        logger = logging.getLogger(__name__)
        logger.info("Logging already configured")
