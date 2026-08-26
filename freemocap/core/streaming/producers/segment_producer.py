"""SegmentProducer — the fitted segment model.

Active while a realtime pipeline is live. Fills SEGMENT_ORIGINS,
ROTATIONS_LOCAL / ROTATIONS_WORLD, and SEGMENT_LENGTHS as self-describing
ChannelBlocks.
"""
from __future__ import annotations


import numpy as np

from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle
from freemocap.core.streaming.channel_helpers import assemble_channel_bytes, origin_landmark_names
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
        origin_names = origin_landmark_names(skeleton.skeleton)
        positions = reconstruction.landmarks if reconstruction else {}
        origin_positions = {name: positions.get(origin_names[name]) for name in segment_names}
        lengths = {
            name: np.array([length], dtype=np.float32)
            for name, length in (
                reconstruction.segment_lengths if reconstruction else {}
            ).items()
        }
        return [
            ChannelBlock(
                kind=ChannelKind.SEGMENT_ORIGINS,
                columns=("x", "y", "z"),
                data=assemble_channel_bytes(names=segment_names, positions=origin_positions, n_cols=3),
            ),
            ChannelBlock(
                kind=ChannelKind.ROTATIONS_LOCAL,
                columns=("w", "x", "y", "z"),
                data=assemble_channel_bytes(
                    names=segment_names,
                    positions=reconstruction.segment_rotations_local if reconstruction else {},
                    n_cols=4,
                ),
            ),
            ChannelBlock(
                kind=ChannelKind.ROTATIONS_WORLD,
                columns=("w", "x", "y", "z"),
                data=assemble_channel_bytes(
                    names=segment_names,
                    positions=reconstruction.segment_rotations_world if reconstruction else {},
                    n_cols=4,
                ),
            ),
            ChannelBlock(
                kind=ChannelKind.SEGMENT_LENGTHS,
                columns=("length_mm",),
                data=assemble_channel_bytes(names=segment_names, positions=lengths, n_cols=1),
            ),
        ]
