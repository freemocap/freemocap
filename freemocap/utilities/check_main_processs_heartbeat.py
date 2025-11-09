import multiprocessing
import os
import signal
import time

import logging
from typing import Final

logger = logging.getLogger(__name__)
HEARTBEAT_INTERVAL_SECONDS: Final[float] = 1.0
HEARTBEAT_TIMEOUT_SECONDS: Final[float] = 30.0
def check_main_process_heartbeat(*,
                                 heartbeat_timestamp: multiprocessing.Value,
                                 global_kill_flag: multiprocessing.Value) -> bool:
    """Check if main process is still alive based on heartbeat."""
    current_time: float = time.perf_counter()
    last_heartbeat: float = heartbeat_timestamp.value

    time_since_heartbeat: float = current_time - last_heartbeat

    if time_since_heartbeat > HEARTBEAT_TIMEOUT_SECONDS:
        logger.error(
            f"Main process heartbeat timeout! "
            f"Last heartbeat was {time_since_heartbeat:.1f}s ago "
            f"(timeout: {HEARTBEAT_TIMEOUT_SECONDS}s)"
        )
        global_kill_flag.value = True
        os.kill(os.getpid(), signal.SIGTERM)
        return False

    return True