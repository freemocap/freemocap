"""Bounded, periodic measurements of live frame delivery."""

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from statistics import mean

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FrameDeliverySample:
    source_seconds: float
    composition_seconds: float
    encoding_seconds: float
    send_seconds: float
    payload_bytes: int


@dataclass(slots=True)
class FrameDeliveryTiming:
    samples: deque[FrameDeliverySample] = field(default_factory=lambda: deque(maxlen=300))
    started_at: float = field(default_factory=time.perf_counter)
    delivered: int = 0

    def record(self, sample: FrameDeliverySample) -> None:
        self.samples.append(sample)
        self.delivered += 1
        now = time.perf_counter()
        elapsed = now - self.started_at
        if elapsed < 5.0:
            return
        logger.info(
            "Live frame delivery: %.1f fps; mean ms: source/wait=%.1f compose=%.1f "
            "encode=%.1f send=%.1f; mean payload=%.1f KiB",
            self.delivered / elapsed,
            mean(item.source_seconds for item in self.samples) * 1000,
            mean(item.composition_seconds for item in self.samples) * 1000,
            mean(item.encoding_seconds for item in self.samples) * 1000,
            mean(item.send_seconds for item in self.samples) * 1000,
            mean(item.payload_bytes for item in self.samples) / 1024,
        )
        self.samples.clear()
        self.started_at = now
        self.delivered = 0
