"""SegmentProducer — the fitted segment model.

Active while a realtime pipeline is live. Fills SEGMENT_ORIGINS,
ROTATIONS_LOCAL / ROTATIONS_WORLD, and SEGMENT_LENGTHS as self-describing
ChannelBlocks.
"""
from __future__ import annotations

from collections.abc import Hashable

import numpy as np

from freemocap.core.streaming.channel_helpers import assemble_channel_bytes, origin_landmark_names
from freemocap.core.streaming.message_model import ChannelBlock, ChannelKind
from freemocap.core.streaming.producers.channel_producer import ChannelProducer
from freemocap.core.streaming.producers.producer_contexts import FrameContext, StreamContext


class SegmentProducer(ChannelProducer):
    def is_active(self, ctx: StreamContext) -> bool:
        return ctx.pipeline_live

    def signature(self, ctx: StreamContext) -> Hashable:
        return (
            "segments",
            tuple(ctx.standard_human.segment_names),
            tuple(sorted((s.name, s.exact_axis.axis) for s in ctx.standard_human.segments)),
        )

    def fill(self, frame_ctx: FrameContext) -> list[ChannelBlock]:
        message = frame_ctx.aggregator_output
        stream_ctx = frame_ctx.stream_context
        if message is None or stream_ctx is None:
            return []
        segment_names = tuple(stream_ctx.standard_human.segment_names)
        origin_names = origin_landmark_names(stream_ctx.standard_human)
        positions = message.standard_skeleton or {}
        origin_positions = {name: positions.get(origin_names[name]) for name in segment_names}
        lengths = {
            name: np.array([length], dtype=np.float32)
            for name, length in (message.segment_lengths or {}).items()
        }
        return [
            ChannelBlock(
                kind=ChannelKind.SEGMENT_ORIGINS,
                names=segment_names,
                columns=("x", "y", "z"),
                data=assemble_channel_bytes(names=segment_names, positions=origin_positions, n_cols=3),
            ),
            ChannelBlock(
                kind=ChannelKind.ROTATIONS_LOCAL,
                names=segment_names,
                columns=("w", "x", "y", "z"),
                data=assemble_channel_bytes(names=segment_names, positions=message.segment_rotations_local or {}, n_cols=4),
            ),
            ChannelBlock(
                kind=ChannelKind.ROTATIONS_WORLD,
                names=segment_names,
                columns=("w", "x", "y", "z"),
                data=assemble_channel_bytes(names=segment_names, positions=message.segment_rotations_world or {}, n_cols=4),
            ),
            ChannelBlock(
                kind=ChannelKind.SEGMENT_LENGTHS,
                names=segment_names,
                columns=("length_mm",),
                data=assemble_channel_bytes(names=segment_names, positions=lengths, n_cols=1),
            ),
        ]
