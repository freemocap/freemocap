"""
PipelineStageTimer: per-node accumulator for stage timings.

Records `elapsed_ms` samples per named stage. Periodically flushes the
accumulated samples to a publication queue as a `PipelineTimingMessage`.
The aggregator runs a `PipelineTimingReporter` thread that subscribes,
maintains rolling windows across all nodes, and prints one consolidated
report (see `pipeline_timing_reporter.py`).
"""
import logging
import time
from dataclasses import dataclass, field
from queue import Full

from freemocap.core.types.type_overloads import TopicPublicationQueue

logger = logging.getLogger(__name__)

FLUSH_INTERVAL_SECONDS: float = 5.0
ROLLING_WINDOW_FRAMES: int = 500


@dataclass
class PipelineStageTimer:
    """Accumulates per-stage elapsed times and flushes them to a pubsub topic."""

    name: str
    flush_interval: float = field(default=FLUSH_INTERVAL_SECONDS)
    last_flush: float = field(default_factory=time.monotonic)
    samples: dict[str, list[float]] = field(default_factory=dict)

    def record(self, stage: str, elapsed_ms: float) -> None:
        if stage not in self.samples:
            self.samples[stage] = []
        self.samples[stage].append(elapsed_ms)

    def maybe_flush(
            self,
            *,
            publication_queue: TopicPublicationQueue,
            node_kind: str,
            camera_id: str | None = None,
    ) -> None:
        from freemocap.pubsub.pubsub_topics import PipelineTimingMessage

        now = time.monotonic()
        if now - self.last_flush < self.flush_interval:
            return
        self.last_flush = now
        if not self.samples:
            return

        batch = {stage: list(values) for stage, values in self.samples.items() if values}
        for values in self.samples.values():
            values.clear()
        if not batch:
            return

        msg = PipelineTimingMessage(
            node_kind=node_kind,
            node_label=self.name,
            camera_id=camera_id,
            samples=batch,
        )
        try:
            publication_queue.put_nowait(msg)
        except Full:
            # Timing is best-effort; drop the batch rather than blocking the pipeline.
            pass
