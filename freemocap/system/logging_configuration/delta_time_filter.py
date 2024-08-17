import logging
from datetime import datetime


class DeltaTimeFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.prev_time = datetime.now().timestamp()

    def filter(self, record: logging.LogRecord) -> bool:
        current_time = datetime.now().timestamp()
        delta_ms = (current_time - self.prev_time) * 1000
        record.delta_t = f"Δt:{delta_ms:.6f}ms"
        self.prev_time = current_time
        return True
