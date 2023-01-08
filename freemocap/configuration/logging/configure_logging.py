import logging
import logging.handlers
import sys
from logging.config import dictConfig

from freemocap.configuration.paths_and_files_names import get_log_file_path

DEFAULT_LOGGING = {"version": 1, "disable_existing_loggers": False}

LOG_FILE_PATH = None


def get_logging_handlers():
    """
    Initialize logging defaults for Project.
    :param logfile_path: logfile used to the logfile
    :type logfile_path: string
    This function does:
    - Assign INFO and DEBUG level to logger file handler and console handler
    """
    dictConfig(DEFAULT_LOGGING)

    default_formatter = logging.Formatter(
        "[%(asctime)s.%(msecs)04d] [%(levelname)8s] [%(name)s] [%(funcName)s():%(lineno)s] [PID:%(process)d "
        "TID:%(thread)d] %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(default_formatter)

    # Setup File handler (from https://stackoverflow.com/a/24507130/14662833 )
    global LOG_FILE_PATH
    LOG_FILE_PATH = get_log_file_path()
    file_handler = logging.FileHandler(LOG_FILE_PATH)
    file_handler.setFormatter(default_formatter)
    file_handler.setLevel(logging.DEBUG)

    return [console_handler, file_handler]


def configure_logging():
    print(f"Setting up freemocap logging  {__file__}")
    handlers = get_logging_handlers()
    for handler in handlers:
        if not handler in logging.getLogger("").handlers:
            logging.getLogger("").handlers.append(handler)

    logging.root.setLevel(logging.DEBUG)
