"""Contexts passed to channel producers.

StreamContext is the structural (schema-time) state: what the producers need to
declare activeness and a change signature — it never carries per-frame values.
FrameContext is the per-frame payload passed to fill().
"""
from __future__ import annotations

from dataclasses import dataclass, field

from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage  # noqa: TC001
from skellyforge.skellymodels.standard_human.standard_human_model import StandardHuman  # noqa: TC002


@dataclass
class StreamContext:
    """Structural only, no per-frame data."""

    standard_human: StandardHuman
    camera_ids: tuple[str, ...] = ()
    camera_image_sizes: dict[str, tuple[int, int]] = field(default_factory=dict)
    tracker_keypoint_names: tuple[str, ...] = ()
    detector_type: str = "rtmpose"
    pipeline_live: bool = False


@dataclass
class FrameContext:
    """Per-frame payload passed to each active producer's fill()."""

    frame_number: int
    timestamp: float
    aggregator_output: AggregationNodeOutputMessage | None = None
    image_payload: bytes | None = None
    stream_context: StreamContext | None = None
