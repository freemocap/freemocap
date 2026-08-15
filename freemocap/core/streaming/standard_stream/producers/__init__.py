"""Channel-producer composition — the schema and each sample are composed from
the active producers, in ``ALL_PRODUCERS`` order.

The schema is the union of the active producers' groups + metadata; a sample
is the concatenation of the active producers' filled blocks. New data types
(face blendshapes, audio, per-camera reprojections) are new producers — no
changes to the codec, the relay, or the consumer's demux.

See `current-work-plans/01-data-model/stream-contract.md` § the producer model.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from collections.abc import Hashable

from freemocap.core.streaming.standard_stream.producers.channel_producer import (
    ChannelProducer,
)
from freemocap.core.streaming.standard_stream.producers.derived_producer import (
    DerivedProducer,
)
from freemocap.core.streaming.standard_stream.producers.image_producer import (
    ImageProducer,
)
from freemocap.core.streaming.standard_stream.producers.keypoints_producer import (
    KeypointsProducer,
)
from freemocap.core.streaming.standard_stream.producers.overlay_producer import (
    OverlayProducer,
)
from freemocap.core.streaming.standard_stream.producers.producer_contexts import (
    FrameContext,
    StreamContext,
)
from freemocap.core.streaming.standard_stream.producers.segment_producer import (
    SegmentProducer,
)
from freemocap.core.streaming.standard_stream.stream_sample import StreamSample
from freemocap.core.streaming.standard_stream.stream_schema import StreamSchema

# Fixed producer order = the schema's channel order and the sample's block
# order. IMAGE_JPEG composes last (its uint8 blob can have an odd byte length,
# which would misalign a following float32 block for aligned typed-array views).
ALL_PRODUCERS: tuple[ChannelProducer, ...] = (
    KeypointsProducer(),
    SegmentProducer(),
    OverlayProducer(),
    DerivedProducer(),
    ImageProducer(),
)

__all__ = [
    "ALL_PRODUCERS",
    "StreamComposition",
    "compose",
    "compose_sample",
    "signature_of",
]


@dataclass(frozen=True)
class StreamComposition:
    """One composed data model: the context it was built from, the schema it
    produced, and the active producers (in order)."""

    context: StreamContext
    schema: StreamSchema
    producers: tuple[ChannelProducer, ...]


def signature_of(ctx: StreamContext) -> Hashable:
    """The composite structural signature of the current data model.

    A change (pipeline start/stop, detector, camera set) changes this tuple —
    the supervisor rebuilds + resends the schema exactly then.
    """
    return tuple(
        producer.signature(ctx)
        for producer in ALL_PRODUCERS
        if producer.is_active(ctx)
    )


def compose(ctx: StreamContext, *, stream_id: str, stream_name: str) -> StreamComposition:
    """Compose the schema for the current data model from the active producers.

    Producer-owned metadata keys never overlap; the merge is order-independent.
    """
    active = tuple(p for p in ALL_PRODUCERS if p.is_active(ctx))
    channels = tuple(g for p in active for g in p.schema_groups(ctx))
    metadata: dict[str, object] = {}
    for producer in active:
        metadata.update(producer.schema_metadata(ctx))
    schema = StreamSchema(
        stream_id=stream_id,
        stream_name=stream_name,
        coordinate_convention=ctx.convention,
        channels=channels,
        **metadata,
    )
    return StreamComposition(context=ctx, schema=schema, producers=active)


def compose_sample(comp: StreamComposition, frame_ctx: FrameContext) -> StreamSample:
    """Compose one sample from the active producers' fills for this frame.

    Binds the composition's ``StreamContext`` onto the frame context so
    stateless producers can resolve the schema's declared names while filling.
    """
    fill_ctx = replace(frame_ctx, stream_context=comp.context)
    blocks = [b for p in comp.producers for b in p.fill(fill_ctx)]
    return StreamSample(
        timestamp=float(frame_ctx.timestamp),
        frame_number=frame_ctx.frame_number,
        subject_id=0,
        blocks=blocks,
    )
