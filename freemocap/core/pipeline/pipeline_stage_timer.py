"""
PipelineStageTimer: per-node accumulator for stage timings.

Records `elapsed_ms` samples per named stage. Periodically flushes the
accumulated samples to a publication queue as a `PipelineTimingMessage`.
The aggregator runs a `PipelineTimingReporter` thread that subscribes,
maintains rolling windows across all nodes, and prints one consolidated
report (see `pipeline_timing_reporter.py`).

Task events with monotonic timestamps are batched alongside legacy elapsed
samples so the metrics timeline can render true start/end bars during migration.
"""
import logging
import time
from dataclasses import dataclass, field
from queue import Full

from freemocap.core.pipeline.pipeline_timing_events import perf_counter_ns
from freemocap.core.pipeline.pipeline_timing_task_ids import CLOCK_DOMAIN_PERF_COUNTER
from freemocap.core.types.type_overloads import TopicPublicationQueue
from freemocap.pubsub.pubsub_topics import PipelineTimingEvent

logger = logging.getLogger(__name__)

# Match websocket pipeline_timing relay (~4 Hz) so the UI receives steady updates.
FLUSH_INTERVAL_SECONDS: float = 0.25
ROLLING_WINDOW_FRAMES: int = 500
MAX_EVENTS_PER_FLUSH: int = 256


@dataclass
class PipelineStageTimer:
    """Accumulates per-stage elapsed times and flushes them to a pubsub topic."""

    name: str
    flush_interval: float = field(default=FLUSH_INTERVAL_SECONDS)
    last_flush: float = field(default_factory=time.perf_counter)
    samples: dict[str, list[float]] = field(default_factory=dict)
    events: list[PipelineTimingEvent] = field(default_factory=list)
    dropped_events: int = 0

    def record(self, stage: str, elapsed_ms: float) -> None:
        if stage not in self.samples:
            self.samples[stage] = []
        self.samples[stage].append(elapsed_ms)

    def record_task_event(self, event: PipelineTimingEvent) -> None:
        if len(self.events) >= MAX_EVENTS_PER_FLUSH:
            self.dropped_events += 1
            return
        self.events.append(event)
        self.record(event.stage, event.duration_ms)

    def record_stage_interval(
            self,
            *,
            event: PipelineTimingEvent,
    ) -> None:
        self.record_task_event(event)

    def extend_task_events(self, events: list[PipelineTimingEvent]) -> None:
        for event in events:
            self.record_task_event(event)

    def maybe_flush(
            self,
            *,
            publication_queue: TopicPublicationQueue,
            node_kind: str,
            camera_id: str | None = None,
    ) -> None:
        from freemocap.pubsub.pubsub_topics import PipelineTimingMessage

        now = time.perf_counter()
        if now - self.last_flush < self.flush_interval:
            return
        self.last_flush = now
        if not self.samples and not self.events:
            return

        batch = {stage: list(values) for stage, values in self.samples.items() if values}
        for values in self.samples.values():
            values.clear()

        events_batch = list(self.events)
        self.events.clear()
        dropped = self.dropped_events
        self.dropped_events = 0

        if not batch and not events_batch:
            return

        msg = PipelineTimingMessage(
            node_kind=node_kind,
            node_label=self.name,
            camera_id=camera_id,
            samples=batch,
            events=events_batch,
            clock_domain=CLOCK_DOMAIN_PERF_COUNTER,
            relay_perf_counter_ns=perf_counter_ns(),
            dropped_timing_events=dropped,
        )
        try:
            publication_queue.put_nowait(msg)
        except Full:
            # Timing is best-effort; drop the batch rather than blocking the pipeline.
            pass
