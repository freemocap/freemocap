"""Contexts passed to channel producers.

``StreamContext`` is the *structural* (schema-time) state: what the producers need
to declare their schema groups, metadata, activeness, and change signature — it
never carries per-frame values. ``FrameContext`` is the per-frame payload passed to
``fill()``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from freemocap.core.streaming.standard_stream.coordinate_convention import (
    FREEMOCAP_COORDINATE_CONVENTION,
    CoordinateConvention,
)

# Imported at runtime (not TYPE_CHECKING-only): beartype resolves these
# annotations from the module namespace.
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage  # noqa: TC001 — resolved at runtime by beartype
from skellyforge.skellymodels.standard_human.standard_human_model import StandardHuman  # noqa: TC002 — resolved at runtime by beartype


@dataclass
class StreamContext:
    """Schema-time context — structural only, no per-frame data.

    The supervisor rebuilds this each time it checks for a data-model change; it
    drives ``is_active`` / ``schema_groups`` / ``schema_metadata`` / ``signature``
    on every producer.
    """

    standard_human: StandardHuman
    camera_ids: tuple[str, ...] = ()
    camera_image_sizes: dict[str, tuple[int, int]] = field(default_factory=dict)
    tracker_keypoint_names: tuple[str, ...] = ()
    detector_type: str = "rtmpose"
    pipeline_live: bool = False
    convention: CoordinateConvention = FREEMOCAP_COORDINATE_CONVENTION


@dataclass
class FrameContext:
    """Per-frame context passed to each active producer's ``fill()``.

    ``aggregator_output`` is present only when a realtime pipeline produced a frame;
    ``image_payload`` is the SkellyCam multi-camera JPEG payload for this frame (the
    ImageProducer's source). Either may be ``None`` — a producer with no data this
    frame returns no blocks. ``stream_context`` is bound by ``compose_sample`` so a
    stateless producer can resolve the schema's declared names while filling.
    """

    frame_number: int
    timestamp: float
    aggregator_output: AggregationNodeOutputMessage | None = None
    image_payload: bytes | None = None
    stream_context: StreamContext | None = None
