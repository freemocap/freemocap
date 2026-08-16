"""Channel-producer composition.

ALL_PRODUCERS is the fixed producer order (the frame's channel order). A frame
is the concatenation of the active producers' filled ChannelBlocks. New data
types are new producers — no changes to the codec, the relay, or the consumer's
demux.
"""
from __future__ import annotations

from collections.abc import Hashable

from freemocap.core.streaming.producers.channel_producer import ChannelProducer
from freemocap.core.streaming.producers.derived_producer import DerivedProducer
from freemocap.core.streaming.producers.keypoints_producer import KeypointsProducer
from freemocap.core.streaming.producers.overlay_producer import OverlayProducer
from freemocap.core.streaming.producers.producer_contexts import StreamContext
from freemocap.core.streaming.producers.segment_producer import SegmentProducer

ALL_PRODUCERS: tuple[ChannelProducer, ...] = (
    KeypointsProducer(),
    SegmentProducer(),
    OverlayProducer(),
    DerivedProducer(),
)


def signature_of(ctx: StreamContext) -> Hashable:
    """The composite structural signature of the current data model.

    A change (pipeline start/stop, detector, camera set, image sizes) changes
    this — the supervisor re-emits the replace-kinds exactly then.
    """
    producer_signatures = tuple(
        producer.signature(ctx) for producer in ALL_PRODUCERS if producer.is_active(ctx)
    )
    camera_layout_signature = (
        "camera_layout",
        tuple(sorted(ctx.camera_ids)),
        tuple(sorted(ctx.camera_image_sizes.items())),
    )
    return (producer_signatures, camera_layout_signature)


__all__ = ["ALL_PRODUCERS", "signature_of"]
