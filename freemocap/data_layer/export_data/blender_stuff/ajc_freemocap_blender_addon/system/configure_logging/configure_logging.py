import logging
import sys
from datetime import datetime
from enum import Enum
from logging.config import dictConfig

from ajc_freemocap_blender_addon.system.configure_logging.utilities import get_hashed_color


class LogLevel(Enum):
    TRACE = 5
    DEBUG = logging.DEBUG  # 10
    INFO = logging.INFO  # 20
    SUCCESS = 25
    WARNING = logging.WARNING  # 30
    ERROR = logging.ERROR  # 40
    CRITICAL = logging.CRITICAL  # 50


logging.addLevelName(LogLevel.TRACE.value, "TRACE")
logging.addLevelName(LogLevel.SUCCESS.value, "SUCCESS")


class DeltaTimeFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.prev_time = datetime.now().timestamp()

    def filter(self, record):
        current_time = datetime.now().timestamp()
        delta = current_time - self.prev_time
        record.delta_t = f"Δt:{delta:.6f}s"
        self.prev_time = current_time
        return True


class CustomFormatter(logging.Formatter):
    """A custom Formatter class to include microseconds in log timestamps."""

    def formatTime(self, record, datefmt=None):
        created = record.created
        if isinstance(created, float) or isinstance(created, int):
            timestamp = created
        else:
            raise TypeError("Invalid type for 'created'")

        date_format_with_microseconds = (
            "%Y-%m-%dT%H:%M:%S.%f"  # Including microseconds with %f
        )
        return datetime.strftime(
            datetime.fromtimestamp(timestamp), date_format_with_microseconds
        )


class LoggerBuilder:
    DEFAULT_LOGGING = {"version": 1, "disable_existing_loggers": False}
    # class BlenderStream:
    #     def write(self, message):
    #         bpy.ops.console.scrollback_append(text=str(message), type='OUTPUT')
    #
    #     def flush(self):
    #         pass

    format_string = (
        "[%(asctime)s] [%(delta_t)s] [%(levelname)8s] [%(name)s] "
        "[%(module)s:%(funcName)s():%(lineno)s] "
        "[PID:%(process)d:%(processName)s TID:%(thread)d:%(threadName)s ] %(message)s"
    )

    def __init__(self, level: LogLevel):
        self.default_logging_formatter = CustomFormatter(
            fmt=self.format_string, datefmt="%Y-%m-%dT%H:%M:%S"
        )
        dictConfig(self.DEFAULT_LOGGING)

        self._set_logging_level(level)

    def _set_logging_level(self, level: LogLevel):
        logging.root.setLevel(level.value)

    # def build_file_handler(self):
    #     file_handler = logging.FileHandler(get_log_file_path(), encoding="utf-8")
    #     file_handler.setLevel(LogLevel.TRACE.value)
    #     file_handler.setFormatter(self.default_logging_formatter)
    #     file_handler.addFilter(DeltaTimeFilter())
    #     return file_handler

    class ColoredConsoleHandler(logging.StreamHandler):
        COLORS = {
            "TRACE": "\033[37m",  # Dark White (grey)
            "DEBUG": "\033[34m",  # Blue
            "INFO": "\033[96m",  # Cyan
            "SUCCESS": "\033[95m",  # Magenta
            "WARNING": "\033[33m",  # Yellow
            "ERROR": "\033[31m",  # Red
            "CRITICAL": "\033[41m",  # Background Red
        }

        def emit(self, record):
            color_code = self.COLORS.get(record.levelname, "\033[0m")
            formatted_record = color_code + self.format(record) + "\033[0m"

            pid_color = get_hashed_color(record.process)
            tid_color = get_hashed_color(record.thread)

            formatted_record = formatted_record.replace(
                f"PID:{record.process}:{record.processName}",
                pid_color + f"PID:{record.process}:{record.processName}" + "\033[0m",
            )
            formatted_record = formatted_record.replace(
                f"TID:{record.thread}:{record.threadName}",
                tid_color + f"TID:{record.thread}:{record.threadName}" + "\033[0m",
            )

            print(formatted_record)

    def build_blender_handler(self):
        blender_stream = self.BlenderStream()
        # Create a logging handler for Blender
        blender_handler = self.ColoredConsoleHandler(stream=blender_stream)
        blender_handler.setLevel(LogLevel.TRACE.value)
        blender_handler.setFormatter(self.default_logging_formatter)
        blender_handler.addFilter(DeltaTimeFilter())

    def build_console_handler(self):
        console_handler = self.ColoredConsoleHandler(stream=sys.stdout)
        console_handler.setLevel(LogLevel.TRACE.value)
        console_handler.setFormatter(self.default_logging_formatter)
        console_handler.addFilter(DeltaTimeFilter())
        return console_handler

    def configure(self):
        if len(logging.getLogger().handlers) == 0:
            # handlers = [self.build_file_handler(), self.build_console_handler()]
            handlers = [self.build_console_handler()]  # self.build_blender_handler()]
            for handler in handlers:
                if handler not in logging.getLogger("").handlers:
                    logging.getLogger("").handlers.append(handler)
        else:
            logger = logging.getLogger(__name__)
            logger.info("Logging already configured")


def configure_logging(level: LogLevel = LogLevel.INFO):
    def trace(self, message, *args, **kws):
        if self.isEnabledFor(LogLevel.TRACE.value):
            self._log(LogLevel.TRACE.value, message, args, **kws, stacklevel=2)

    logging.Logger.trace = trace

    def success(self, message, *args, **kws):
        if self.isEnabledFor(LogLevel.SUCCESS.value):
            self._log(LogLevel.SUCCESS.value, message, args, **kws, stacklevel=2)

    logging.Logger.success = success

    builder = LoggerBuilder(level)
    builder.configure()


def log_test_messages(logger):
    logger.trace("This is a TRACE message.")
    logger.debug("This is a DEBUG message.")
    logger.info("This is an INFO message.")
    logger.success("This is a SUCCESS message.")
    logger.warning("This is a WARNING message.")
    logger.error("This is an ERROR message.")
    logger.critical("This is a CRITICAL message.")

    print("----------This is a print message.------------------")

    import time

    for iter in range(1, 10):
        wait_time = iter / 10
        print(f"Testing timestamps (round: {iter}:")
        logger.info(
            "Starting 1 sec timer (Δt should probably be near 0, unless you've got other stuff going on)"
        )
        tic = time.perf_counter_ns()
        time.sleep(wait_time)
        toc = time.perf_counter_ns()
        elapsed_time = (toc - tic) / 1e9
        logger.info(
            f"Done {wait_time} sec timer - elapsed time:{elapsed_time} (Δt should be ~{wait_time}s)"
        )


if __name__ == "__main__":
    from ajc_freemocap_blender_addon import get_logger

    logger = get_logger()
    configure_logging(LogLevel.TRACE)  # Setting the root logger level to TRACE
    log_test_messages(logger)
    logger.success(
        "Logging setup and tests completed. Check the console output and the log file."
    )
