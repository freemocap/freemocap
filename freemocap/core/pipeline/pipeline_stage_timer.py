"""
PipelineStageTimer: per-node accumulator for stage timings.

Records `elapsed_ms` samples per named stage. Periodically flushes the
accumulated samples to a publication queue as a `PipelineTimingMessage`.
The aggregator runs a `PipelineTimingReporter` thread that subscribes,
maintains rolling windows across all nodes, and prints one consolidated
report (see `pipeline_timing_reporter.py`).

Task events with perf_counter timestamps are batched alongside legacy elapsed
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

# Flush every N captured frames. The wall-clock interval is derived from the
# capture frame rate (N / fps) and computed once per pipeline in
# `flush_interval_for_fps`, then passed to each node's timer.
FRAMES_PER_FLUSH: int = 5
# Fallback interval used only when the capture frame rate is unknown.
DEFAULT_FLUSH_INTERVAL_SECONDS: float = 0.25
ROLLING_WINDOW_FRAMES: int = 500
MAX_EVENTS_PER_FLUSH: int = 256


def flush_interval_for_fps(capture_fps: float | None) -> float:
    """Return the flush interval (seconds) for ``FRAMES_PER_FLUSH`` frames at ``capture_fps``.

    Falls back to ``DEFAULT_FLUSH_INTERVAL_SECONDS`` when the frame rate is unknown.
    """
    if capture_fps is not None and capture_fps > 0:
        return FRAMES_PER_FLUSH / capture_fps
    return DEFAULT_FLUSH_INTERVAL_SECONDS


@dataclass
class PipelineStageTimer:
    """Accumulates per-stage elapsed times and flushes them to a pubsub topic."""

    name: str
    flush_interval: float | None = None
    last_flush: float = field(default_factory=time.perf_counter)
    start_time: float | None = None
    samples: dict[str, list[float]] = field(default_factory=dict)
    events: list[PipelineTimingEvent] = field(default_factory=list)
    dropped_events: int = 0

    def __post_init__(self) -> None:
        if self.flush_interval is None:
            self.flush_interval = DEFAULT_FLUSH_INTERVAL_SECONDS
        if self.start_time is not None:
            self.last_flush = self.start_time

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
        if self.flush_interval > 0:
            if now - self.last_flush < self.flush_interval:
                return
            # Snap last_flush to the next aligned interval boundary so all nodes
            # that share the same start_time flush at identical absolute times.
            anchor = self.start_time if self.start_time is not None else self.last_flush
            elapsed_since_anchor = now - anchor
            completed_intervals = int(elapsed_since_anchor // self.flush_interval)
            self.last_flush = anchor + (completed_intervals + 1) * self.flush_interval
        # A non-positive flush_interval flushes on every call (used by tests).
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
