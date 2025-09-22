import logging
import multiprocessing
from typing import Optional

from freemocap.system.logging_configuration.handlers.websocket_log_queue_handler import create_websocket_log_queue
from freemocap.system.logging_configuration.log_levels import LogLevels
from freemocap.system.logging_configuration.package_log_quieters import suppress_noisy_package_logs
from .log_test_messages import log_test_messages
from .logger_builder import LoggerBuilder

suppress_noisy_package_logs()
# Add custom log levels
logging.addLevelName(LogLevels.GUI.value, "GUI")
logging.addLevelName(LogLevels.LOOP.value, "LOOP")
logging.addLevelName(LogLevels.TRACE.value, "TRACE")
logging.addLevelName(LogLevels.SUCCESS.value, "SUCCESS")
logging.addLevelName(LogLevels.API.value, "API")


def add_log_method(level: LogLevels, name: str):
    def log_method(self, message, *args, **kws):
        if self.isEnabledFor(level.value):
            self._log(level.value, message, args, **kws, stacklevel=2)

    setattr(logging.Logger, name, log_method)


def configure_logging(level: LogLevels, ws_queue: Optional[multiprocessing.Queue] = None):
    if ws_queue is None:
        # do not create new queue if not main process
        if not multiprocessing.current_process().name.lower() == 'mainprocess':
            return

        ws_queue = create_websocket_log_queue()
    add_log_method(LogLevels.GUI, 'gui')
    add_log_method(LogLevels.LOOP, 'loop')
    add_log_method(LogLevels.TRACE, 'trace')
    add_log_method(LogLevels.API, 'api')
    add_log_method(LogLevels.SUCCESS, 'success')

    builder = LoggerBuilder(level, ws_queue)
    builder.configure()


if __name__ == "__main__":
    logger_test = logging.getLogger(__name__)
    log_test_messages(logger_test)
    logger_test.success(
        "Logging setup and tests completed. Check the console output and the log file."
    )
