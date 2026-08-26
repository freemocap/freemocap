"""The channel-producer contract.

A producer owns a coherent slice of the frame's channels and fills them per
frame as self-describing ChannelBlocks (kind + names + columns + data inline).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle
from freemocap.core.streaming.message_model import ChannelBlock
from freemocap.core.streaming.producers.producer_contexts import FrameContext, StreamContext


@runtime_checkable
class ChannelProducer(Protocol):
    """One channel-producing slice of the data model.

    All methods are pure functions of their context. The producer order in
    ALL_PRODUCERS is the frame's channel order.
    """

    def is_active(self, ctx: StreamContext) -> bool: ...

    def fill(
        self, frame_ctx: FrameContext, skeleton: TrackedSkeletonBundle
    ) -> list[ChannelBlock]:
        """This frame's channel block(s) for ONE skeleton; empty when it has no data.

        Called once per tracked skeleton. A producer reads that skeleton's reconstruction
        by `model_id` and never sees the others, which is what stops one model's channels
        being filled from another's data.
        """
        ...
