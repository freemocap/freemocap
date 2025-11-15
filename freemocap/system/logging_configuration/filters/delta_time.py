import logging
from datetime import datetime


class DeltaTimeFilter(logging.Filter):
    """Adds Δt since last log to records"""

    def __init__(self):
        self.prev_time = datetime.now().timestamp()
        super().__init__()

    def filter(self, record: logging.LogRecord) -> bool:
        current_time = datetime.now().timestamp()
        record.delta_t = f"{(current_time - self.prev_time) * 1000:.3f}ms"
        self.prev_time = current_time
        return True
