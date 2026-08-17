"""The channel-producer contract.

A producer owns a coherent slice of the frame's channels and fills them per
frame as self-describing ChannelBlocks (kind + names + columns + data inline).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from freemocap.core.streaming.message_model import ChannelBlock
from freemocap.core.streaming.producers.producer_contexts import FrameContext, StreamContext


@runtime_checkable
class ChannelProducer(Protocol):
    """One channel-producing slice of the data model.

    All methods are pure functions of their context. The producer order in
    ALL_PRODUCERS is the frame's channel order.
    """

    def is_active(self, ctx: StreamContext) -> bool: ...

    def fill(self, frame_ctx: FrameContext) -> list[ChannelBlock]:
        """The self-describing channel block(s) for this frame; an empty list
        when there is no data this frame."""
        ...
