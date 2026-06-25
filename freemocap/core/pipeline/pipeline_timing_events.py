"""Helpers for pipeline task events and skellytracker timing integration."""
from __future__ import annotations

import inspect
import time
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from freemocap.core.pipeline.pipeline_timing_task_ids import (
    batch_task_id,
    per_camera_task_id,
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
    return time.perf_counter_ns()


def call_with_supported_kwargs(
        fn: Callable[..., Any],
        /,
        *args: Any,
        **kwargs: Any,
) -> Any:
    """Invoke ``fn`` passing only keyword arguments it accepts."""
    supported = inspect.signature(fn).parameters
    filtered = {key: value for key, value in kwargs.items() if key in supported}
    return fn(*args, **filtered)


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
    """Read task events from a tracker session, synthesizing when unavailable."""
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


def make_stage_interval_event(
        *,
        frame_number: int,
        stage: str,
        node_kind: str,
        start_time_ns: int,
        end_time_ns: int,
        camera_id: str | None = None,
        parent_task_ids: list[str] | None = None,
        batch_index: int | None = None,
        batch_size: int | None = None,
        task_id: str | None = None,
) -> PipelineTimingEvent:
    duration_ms = max(0.0, (end_time_ns - start_time_ns) / 1_000_000)
    if task_id is None:
        if node_kind == "aggregator":
            from freemocap.core.pipeline.pipeline_timing_task_ids import aggregator_task_id

            task_id = aggregator_task_id(frame_number=frame_number, stage=stage)
        elif camera_id is not None:
            task_id = per_camera_task_id(
                frame_number=frame_number,
                camera_id=camera_id,
                node_kind=node_kind,
                stage=stage,
            )
        else:
            task_id = batch_task_id(
                frame_number=frame_number,
                node_kind=node_kind,
                stage=stage,
            )
    return PipelineTimingEvent(
        task_id=task_id,
        parent_task_ids=list(parent_task_ids or []),
        stage=stage,
        node_kind=node_kind,
        camera_id=camera_id,
        frame_number=frame_number,
        start_time_ns=start_time_ns,
        end_time_ns=end_time_ns,
        duration_ms=duration_ms,
        batch_index=batch_index,
        batch_size=batch_size,
    )


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
