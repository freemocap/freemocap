"""Helpers for pipeline task events and skellytracker timing integration."""
from __future__ import annotations

import time
from collections.abc import Iterable, Mapping
from typing import Any

from freemocap.core.pipeline.pipeline_timing_task_ids import (
    batch_task_id,
)
from freemocap.pubsub.pubsub_topics import PipelineTimingEvent

RTMPOSE_BATCH_STAGES: tuple[str, ...] = (
    "human_detection_letterbox",
    "human_detection_batch_pack",
    "human_detection_preprocess",
    "human_detection",
    "human_detection_postprocess",
    "pose_estimation_preprocess",
    "pose_estimation",
    "pose_estimation_postprocess",
)

_SKELLYTRACKER_STAGE_ATTRS: tuple[tuple[str, str], ...] = tuple(
    (stage, f"last_{stage}_ms") for stage in RTMPOSE_BATCH_STAGES
)


def perf_counter_ns() -> int:
    """Cross-process comparable high-resolution clock in nanoseconds."""
    return time.perf_counter_ns()


def tracker_events_to_pipeline_events(
        tracker_events: Iterable[Any],
        *,
        node_kind: str,
        default_frame_number: int | None = None,
        default_camera_id: str | None = None,
) -> list[PipelineTimingEvent]:
    """Convert skellytracker timing events into ``PipelineTimingEvent`` records."""
    converted: list[PipelineTimingEvent] = []
    for raw in tracker_events:
        if raw is None:
            continue
        if isinstance(raw, PipelineTimingEvent):
            converted.append(raw)
            continue
        if isinstance(raw, Mapping):
            data = raw
        else:
            data = {
                "task_id": getattr(raw, "task_id", ""),
                "parent_task_ids": getattr(raw, "parent_task_ids", None),
                "stage": getattr(raw, "stage", ""),
                "node_kind": getattr(raw, "node_kind", node_kind),
                "camera_id": getattr(raw, "camera_id", default_camera_id),
                "frame_number": getattr(raw, "frame_number", default_frame_number),
                "start_time_ns": getattr(raw, "start_time_ns", 0),
                "end_time_ns": getattr(raw, "end_time_ns", 0),
                "duration_ms": getattr(raw, "duration_ms", 0.0),
                "batch_index": getattr(raw, "batch_index", None),
                "batch_size": getattr(raw, "batch_size", None),
            }
        parent_ids = data.get("parent_task_ids") or []
        if isinstance(parent_ids, str):
            parent_ids = [parent_ids]
        converted.append(
            PipelineTimingEvent(
                task_id=str(data.get("task_id", "")),
                parent_task_ids=[str(pid) for pid in parent_ids if pid],
                stage=str(data.get("stage", "")),
                node_kind=str(data.get("node_kind", node_kind)),
                camera_id=data.get("camera_id", default_camera_id),
                frame_number=data.get("frame_number", default_frame_number),
                start_time_ns=int(data.get("start_time_ns", 0)),
                end_time_ns=int(data.get("end_time_ns", 0)),
                duration_ms=float(data.get("duration_ms", 0.0)),
                batch_index=data.get("batch_index"),
                batch_size=data.get("batch_size"),
            ),
        )
    return converted


def collect_tracker_batch_events(
        session: Any,
        *,
        node_kind: str,
        frame_number: int,
        camera_ids: list[str] | None = None,
        batch_parent_task_id: str | None = None,
        batch_start_time_ns: int | None = None,
        tracker_events: Iterable[Any] | None = None,
) -> list[PipelineTimingEvent]:
    """Read task events from a tracker session, synthesizing when unavailable.

    Falls back to ``synthesize_rtmpose_batch_events`` only when no events are
    available through the primary ``event_collector`` or ``TrackerTaskEvent``
    attributes.  The synthesizer reads ``last_*_ms`` attributes that exist only
    on ``OnnxSession`` — for ``MediaPipeSession`` (and any other non-ONNX
    session) those attributes are absent, so the synthesizer produces an empty
    list.  This is expected: the non-ONNX path always provides events via the
    ``event_collector`` passed to ``Tracker.process_batch()``.
    """
    if tracker_events is not None:
        events = tracker_events_to_pipeline_events(
            tracker_events,
            node_kind=node_kind,
            default_frame_number=frame_number,
        )
        if events:
            return events

    for attr in ("last_batch_timing_events", "batch_timing_events"):
        raw_events = getattr(session, attr, None)
        if raw_events:
            events = tracker_events_to_pipeline_events(
                raw_events,
                node_kind=node_kind,
                default_frame_number=frame_number,
            )
            if events:
                return events

    return synthesize_rtmpose_batch_events(
        session,
        frame_number=frame_number,
        node_kind=node_kind,
        camera_ids=camera_ids,
        batch_parent_task_id=batch_parent_task_id,
        batch_start_time_ns=batch_start_time_ns,
    )


def synthesize_rtmpose_batch_events(
        session: Any,
        *,
        frame_number: int,
        node_kind: str,
        camera_ids: list[str] | None = None,
        batch_parent_task_id: str | None = None,
        batch_start_time_ns: int | None = None,
) -> list[PipelineTimingEvent]:
    """Build ordered batch task events from legacy ``last_*_ms`` attrs."""
    cursor = batch_start_time_ns if batch_start_time_ns is not None else perf_counter_ns()
    batch_size = len(camera_ids) if camera_ids else None
    events: list[PipelineTimingEvent] = []

    predict_batch_task_id = batch_task_id(
        frame_number=frame_number,
        node_kind=node_kind,
        stage="predict_batch",
    )
    preprocess_child_stages = frozenset({
        "human_detection_letterbox",
        "human_detection_batch_pack",
    })
    preprocess_task_id = batch_task_id(
        frame_number=frame_number,
        node_kind=node_kind,
        stage="human_detection_preprocess",
    )
    preprocess_start_ns: int | None = None
    preprocess_end_ns: int | None = None

    for stage, attr in _SKELLYTRACKER_STAGE_ATTRS:
        duration_ms = float(getattr(session, attr, 0.0))
        if duration_ms <= 0.0:
            continue
        if stage == "human_detection_preprocess":
            continue

        duration_ns = int(duration_ms * 1_000_000)
        start_ns = cursor
        end_ns = start_ns + duration_ns
        stage_parent_ids = [predict_batch_task_id]
        if stage in preprocess_child_stages:
            stage_parent_ids = [preprocess_task_id]
            if preprocess_start_ns is None:
                preprocess_start_ns = start_ns
            preprocess_end_ns = end_ns

        events.append(
            PipelineTimingEvent(
                task_id=batch_task_id(
                    frame_number=frame_number,
                    node_kind=node_kind,
                    stage=stage,
                ),
                parent_task_ids=stage_parent_ids,
                stage=stage,
                node_kind=node_kind,
                frame_number=frame_number,
                start_time_ns=start_ns,
                end_time_ns=end_ns,
                duration_ms=duration_ms,
                batch_size=batch_size,
            ),
        )
        cursor = end_ns

    if preprocess_start_ns is not None and preprocess_end_ns is not None:
        preprocess_duration_ms = (preprocess_end_ns - preprocess_start_ns) / 1_000_000
        events.append(
            PipelineTimingEvent(
                task_id=preprocess_task_id,
                parent_task_ids=[predict_batch_task_id],
                stage="human_detection_preprocess",
                node_kind=node_kind,
                frame_number=frame_number,
                start_time_ns=preprocess_start_ns,
                end_time_ns=preprocess_end_ns,
                duration_ms=preprocess_duration_ms,
                batch_size=batch_size,
            ),
        )

    stage_order = {stage: index for index, stage in enumerate(RTMPOSE_BATCH_STAGES)}
    events.sort(key=lambda event: (stage_order.get(event.stage, len(stage_order)), event.start_time_ns))
    return events


class PipelineTimingEventStore:
    """Rolling, frame-keyed event buffer that survives drain cycles.

    Events are upserted by ``task_id`` so a node that flushes later than its
    peers does not lose its bars before the next websocket drain. Retention is
    frame-based: framed events older than ``retain_frames`` behind the newest
    frame are dropped, and contextless (``frame_number is None``) events are
    bounded by count using a monotonic ``_seen`` sequence.
    """

    def __init__(self) -> None:
        self._events: dict[str, PipelineTimingEvent] = {}
        self._seen: dict[str, int] = {}
        self._counter = 0

    def ingest(self, events: Iterable[PipelineTimingEvent]) -> None:
        for event in events:
            self._counter += 1
            self._events[event.task_id] = event
            self._seen[event.task_id] = self._counter

    def prune(self, *, retain_frames: int, max_contextless: int) -> None:
        framed = [
            event.frame_number
            for event in self._events.values()
            if event.frame_number is not None
        ]
        if framed:
            min_frame = max(framed) - retain_frames
            for task_id in list(self._events):
                event = self._events[task_id]
                if event.frame_number is not None and event.frame_number < min_frame:
                    self._remove(task_id)

        contextless = [
            task_id
            for task_id, event in self._events.items()
            if event.frame_number is None
        ]
        if len(contextless) > max_contextless:
            contextless.sort(key=lambda tid: self._seen.get(tid, 0))
            for task_id in contextless[: len(contextless) - max_contextless]:
                self._remove(task_id)

    def _remove(self, task_id: str) -> None:
        self._events.pop(task_id, None)
        self._seen.pop(task_id, None)

    @property
    def latest_frame(self) -> int | None:
        framed = [
            event.frame_number
            for event in self._events.values()
            if event.frame_number is not None
        ]
        return max(framed) if framed else None

    def snapshot(self) -> list[PipelineTimingEvent]:
        return list(self._events.values())

    def clear(self) -> None:
        self._events.clear()
        self._seen.clear()


def cap_events_by_frame_window(
        events: list[PipelineTimingEvent],
        *,
        frame_window: int = 5,
        frame_buffer: int = 2,
) -> tuple[list[PipelineTimingEvent], int]:
    """Keep events intersecting the latest ``frame_window`` frames plus buffer."""
    framed = [event for event in events if event.frame_number is not None]
    if not framed:
        return events, 0

    latest_frame = max(event.frame_number for event in framed if event.frame_number is not None)
    min_frame = latest_frame - frame_window - frame_buffer + 1
    kept: list[PipelineTimingEvent] = []
    dropped = 0
    for event in events:
        if event.frame_number is None or event.frame_number >= min_frame:
            kept.append(event)
        else:
            dropped += 1
    return kept, dropped


def compute_timing_lag_info(
        events: list[PipelineTimingEvent],
        *,
        configured_fps_hz: float | None = None,
        last_seen: dict[str, float] | None = None,
        now: float | None = None,
) -> dict[str, object]:
    """Compute per-node-kind lag and incomplete-frame metadata without dropping events.

    Returns a ``lag_info`` dict:
    - ``node_lag``: frames each node kind is behind the leader
    - ``incomplete_frames``: frame numbers missing one or more node kinds
    - ``stale_nodes``: node kinds excluded due to staleness timeout
    - ``safe_latest_frame``: latest frame all active node kinds have reached
      (``None`` when no framed events are present or all nodes are stale)

    The caller applies the ``safe_latest_frame`` ceiling to a send-time snapshot;
    this function never removes events.
    """
    import time as _time
    if now is None:
        now = _time.perf_counter()

    # Compute latest frame per node kind.
    latest_per_kind: dict[str, int] = {}
    for event in events:
        if event.frame_number is None:
            continue
        node_kind = event.node_kind or "unknown"
        current = latest_per_kind.get(node_kind)
        if current is None or event.frame_number > current:
            latest_per_kind[node_kind] = event.frame_number

    if not latest_per_kind:
        return {
            "node_lag": {},
            "incomplete_frames": [],
            "stale_nodes": [],
            "safe_latest_frame": None,
        }

    # Determine staleness threshold: max(0.5s, 15 frame periods).
    staleness_s = 0.5
    if configured_fps_hz and configured_fps_hz > 0:
        staleness_s = max(staleness_s, 15.0 / configured_fps_hz)

    stale_nodes: list[str] = []
    included_frames: list[int] = []
    for node_kind, frame in latest_per_kind.items():
        if last_seen is None or node_kind not in last_seen:
            # Never reported — still coming online, include it.
            included_frames.append(frame)
        elif now - last_seen[node_kind] > staleness_s:
            # Stalled — exclude from min.
            stale_nodes.append(node_kind)
        else:
            included_frames.append(frame)

    if not included_frames:
        return {
            "node_lag": {},
            "incomplete_frames": [],
            "stale_nodes": stale_nodes,
            "safe_latest_frame": None,
        }

    safe_latest_frame = min(included_frames)

    # Build lag info: how far each node kind is behind the leader.
    leader_frame = max(latest_per_kind.values())
    node_lag: dict[str, int] = {}
    for node_kind, frame in latest_per_kind.items():
        lag = leader_frame - frame
        if lag > 0:
            node_lag[node_kind] = lag

    # Identify incomplete frames: frames beyond safe_latest_frame but within
    # the frame window (at most 50 frames ahead to bound the set).
    incomplete_frames: list[int] = []
    for event in events:
        fn = event.frame_number
        if fn is not None and fn > safe_latest_frame and fn <= safe_latest_frame + 50:
            if fn not in incomplete_frames:
                incomplete_frames.append(fn)
    incomplete_frames.sort()

    return {
        "node_lag": node_lag,
        "incomplete_frames": incomplete_frames,
        "stale_nodes": stale_nodes,
        "safe_latest_frame": safe_latest_frame,
    }
