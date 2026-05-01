import collections
import logging
import time
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)

REPORT_INTERVAL_SECONDS: float = 10.0
ROLLING_WINDOW_FRAMES: int = 500

@dataclass
class PipelineStageTimer:
    """
    Records per-stage elapsed times, logs each one at TRACE level, and
    prints a rolling statistics report at INFO level every N seconds.
    """

    name:str
    report_interval:float = field(default=REPORT_INTERVAL_SECONDS)
    last_report: float = field(default_factory=time.monotonic)
    samples: dict[str, collections.deque] = field(default_factory=dict)


    def record(self, stage: str, elapsed_ms: float) -> None:
        if stage not in self.samples:
            self.samples[stage] = collections.deque(maxlen=ROLLING_WINDOW_FRAMES)
        self.samples[stage].append(elapsed_ms)

    def maybe_report(self) -> None:
        now = time.monotonic()
        if now - self.last_report >= self.report_interval:
            self.last_report = now
            self.print_report()

    def print_report(self) -> None:
        if not self.samples:
            return
        sep = "=" * 72
        lines = [f"\n{sep}", f"  Pipeline Timing Report — {self.name}", sep]
        for stage, deq in sorted(self.samples.items()):
            arr = np.array(deq)
            n = len(arr)
            lines.append(
                f"  {stage:<42s}  n={n:4d}  "
                f"mean={np.mean(arr):7.2f}ms  "
                f"p50={np.median(arr):7.2f}ms  "
                f"p95={np.percentile(arr, 95):7.2f}ms  "
                f"max={np.max(arr):7.2f}ms"
            )
        lines.append(sep)
        logger.trace("\n".join(lines))
