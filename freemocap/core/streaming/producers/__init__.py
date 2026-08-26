"""Channel-producer composition.

ALL_PRODUCERS is the fixed producer order (the frame's channel order). A frame
is the concatenation of the active producers' filled ChannelBlocks. New data
types are new producers — no changes to the codec, the relay, or the consumer's
demux.
"""
from __future__ import annotations

from freemocap.core.streaming.producers.channel_producer import ChannelProducer
from freemocap.core.streaming.producers.derived_producer import DerivedProducer
from freemocap.core.streaming.producers.joint_angles_producer import JointAnglesProducer
from freemocap.core.streaming.producers.keypoints_producer import KeypointsProducer
from freemocap.core.streaming.producers.overlay_producer import OverlayProducer
from freemocap.core.streaming.producers.segment_producer import SegmentProducer
ALL_PRODUCERS: tuple[ChannelProducer, ...] = (
    KeypointsProducer(),
    SegmentProducer(),
    OverlayProducer(),
    DerivedProducer(),
    JointAnglesProducer(),
)

__all__ = ["ALL_PRODUCERS"]
