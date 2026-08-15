"""The channel-producer contract.

A producer owns a coherent slice of the stream's data model and declares how
to (a) describe it in the schema and (b) fill it per frame. See
`current-work-plans/01-data-model/stream-contract.md` § the producer model.
"""
from __future__ import annotations

from collections.abc import Hashable
from typing import Protocol, runtime_checkable

from freemocap.core.streaming.standard_stream.producers.producer_contexts import (
    FrameContext,
    StreamContext,
)
from freemocap.core.streaming.standard_stream.stream_sample import SampleBlock
from freemocap.core.streaming.standard_stream.stream_schema import ChannelGroup


@runtime_checkable
class ChannelProducer(Protocol):
    """One channel-producing slice of the data model.

    All methods are pure functions of their context — no mutable state. The
    producer order in ``ALL_PRODUCERS`` is the schema's channel order and the
    sample's block order.
    """

    def is_active(self, ctx: StreamContext) -> bool: ...

    def schema_groups(self, ctx: StreamContext) -> list[ChannelGroup]: ...

    def schema_metadata(self, ctx: StreamContext) -> dict[str, object]:
        """Static StreamSchema fields this producer owns (keyed by field name).

        Producer-owned keys never overlap; the composer merges them into the
        StreamSchema constructor.
        """
        ...

    def signature(self, ctx: StreamContext) -> Hashable:
        """A structural fingerprint — NOT per-frame values — for change detection."""
        ...

    def fill(self, frame_ctx: FrameContext) -> list[SampleBlock]:
        """The block(s) for this frame; no data this frame → an empty list."""
        ...
