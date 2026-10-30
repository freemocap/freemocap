"""SegmentProducer — the fitted segment model.

Active while a realtime pipeline is live. Fills SEGMENT_ORIGINS,
ROTATIONS_LOCAL / ROTATIONS_WORLD, and SEGMENT_LENGTHS as self-describing
ChannelBlocks.
"""
from __future__ import annotations


import numpy as np

from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle
from freemocap.core.streaming.channel_helpers import assemble_channel_bytes
from freemocap.core.streaming.message_model import ChannelBlock, ChannelKind
from freemocap.core.streaming.producers.channel_producer import ChannelProducer
from freemocap.core.streaming.producers.producer_contexts import FrameContext, StreamContext


class SegmentProducer(ChannelProducer):
    def is_active(self, ctx: StreamContext) -> bool:
        return ctx.pipeline_live

    def fill(
        self, frame_ctx: FrameContext, skeleton: TrackedSkeletonBundle
    ) -> list[ChannelBlock]:
        message = frame_ctx.aggregator_output
        if message is None:
            return []
        reconstruction = message.reconstructions.get(skeleton.model_id)
        segment_names = tuple(skeleton.skeleton.segments)
        origin_positions = reconstruction.segment_origins if reconstruction else {}
        lengths = reconstruction.segment_lengths if reconstruction else {}
        return [
            ChannelBlock(
                kind=ChannelKind.SEGMENT_ORIGINS,
                columns=("x", "y", "z"),
                data=assemble_channel_bytes(names=segment_names, positions=origin_positions, columns=("x", "y", "z")),
            ),
            ChannelBlock(
                kind=ChannelKind.ROTATIONS_LOCAL,
                columns=("w", "x", "y", "z"),
                data=assemble_channel_bytes(
                    names=segment_names,
                    positions=reconstruction.segment_rotations_local if reconstruction else {},
                    columns=("w", "x", "y", "z"),
                ),
            ),
            ChannelBlock(
                kind=ChannelKind.ROTATIONS_WORLD,
                columns=("w", "x", "y", "z"),
                data=assemble_channel_bytes(
                    names=segment_names,
                    positions=reconstruction.segment_rotations_world if reconstruction else {},
                    columns=("w", "x", "y", "z"),
                ),
            ),
            ChannelBlock(
                kind=ChannelKind.SEGMENT_LENGTHS,
                columns=("length_mm",),
                data=assemble_channel_bytes(names=segment_names, positions=lengths, columns=("length_mm",)),
            ),
        ]
