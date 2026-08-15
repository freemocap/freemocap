"""SegmentProducer — the fitted segment model.

Active while a realtime pipeline is live. Contributes ``SEGMENT_ORIGINS``,
``ROTATIONS_LOCAL`` / ``ROTATIONS_WORLD``, and the per-frame
``SEGMENT_LENGTHS`` block; owns the schema's hierarchy metadata
(``connections`` / ``joint_hierarchy`` / ``segment_parents``), the
``rest_pose``, and the anthropometric default ``segment_lengths`` (the live
estimates ride the sample, so length changes never touch the schema).
"""
from __future__ import annotations

from collections.abc import Hashable

import numpy as np

from freemocap.core.streaming.standard_stream.producers.channel_producer import (
    ChannelProducer,
)
from freemocap.core.streaming.standard_stream.producers.producer_contexts import (
    FrameContext,
    StreamContext,
)
from freemocap.core.streaming.standard_stream.sample_block_helpers import (
    assemble_rows,
    origin_landmark_names,
)
from freemocap.core.streaming.standard_stream.stream_sample import SampleBlock
from freemocap.core.streaming.standard_stream.stream_schema import (
    ROTATION_COLUMNS,
    SEGMENT_LENGTHS_COLUMNS,
    SEGMENT_ORIGINS_COLUMNS,
    ChannelGroup,
    ChannelKind,
    RestPose,
    _merge_segment_lengths,
)


class SegmentProducer(ChannelProducer):
    def is_active(self, ctx: StreamContext) -> bool:
        return ctx.pipeline_live

    def schema_groups(self, ctx: StreamContext) -> list[ChannelGroup]:
        segment_names = tuple(ctx.standard_human.segment_names)
        units = ctx.convention.units.value
        return [
            ChannelGroup(
                kind=ChannelKind.SEGMENT_ORIGINS,
                names=segment_names,
                columns=SEGMENT_ORIGINS_COLUMNS,
                units=units,
            ),
            ChannelGroup(
                kind=ChannelKind.ROTATIONS_LOCAL,
                names=segment_names,
                columns=ROTATION_COLUMNS,
                units="quaternion",
            ),
            ChannelGroup(
                kind=ChannelKind.ROTATIONS_WORLD,
                names=segment_names,
                columns=ROTATION_COLUMNS,
                units="quaternion",
            ),
            ChannelGroup(
                kind=ChannelKind.SEGMENT_LENGTHS,
                names=segment_names,
                columns=SEGMENT_LENGTHS_COLUMNS,
                units=units,
            ),
        ]

    def schema_metadata(self, ctx: StreamContext) -> dict[str, object]:
        standard_human = ctx.standard_human
        connections = tuple(
            (segment.name, child.name)
            for segment in standard_human.segments
            for child in standard_human.get_children(segment.name)
        )
        return {
            "connections": connections,
            "joint_hierarchy": {
                key: tuple(value)
                for key, value in standard_human.joint_hierarchy.items()
            },
            "segment_parents": dict(standard_human.segment_parents),
            # Per-segment long-axis basis name (the EXACT axis declaration):
            # body/hand segments declare +Y, face segments declare +Z. The 3D
            # bone renderer orients the unit geometry onto it.
            "segment_axes": {
                segment.name: segment.exact_axis.axis
                for segment in standard_human.segments
            },
            "rest_pose": RestPose.from_standard_human(standard_human),
            # Anthropometric defaults; the live estimates ride the per-frame
            # SEGMENT_LENGTHS block.
            "segment_lengths": _merge_segment_lengths(standard_human),
        }

    def signature(self, ctx: StreamContext) -> Hashable:
        return (
            "segments",
            tuple(ctx.standard_human.segment_names),
            tuple(
                sorted(
                    (s.name, s.exact_axis.axis)
                    for s in ctx.standard_human.segments
                )
            ),
        )

    def fill(self, frame_ctx: FrameContext) -> list[SampleBlock]:
        message = frame_ctx.aggregator_output
        stream_ctx = frame_ctx.stream_context
        if message is None or stream_ctx is None:
            return []
        standard_human = stream_ctx.standard_human
        segment_names = tuple(standard_human.segment_names)
        origin_names = origin_landmark_names(standard_human)

        positions: dict[str, np.ndarray] = message.standard_skeleton or {}
        origin_positions = {
            name: positions.get(origin_names[name]) for name in segment_names
        }

        lengths: dict[str, np.ndarray] = {}
        if message.segment_lengths:
            for name, length in message.segment_lengths.items():
                lengths[name] = np.array([length], dtype=np.float32)

        blocks: list[SampleBlock] = [
            SampleBlock(
                kind=ChannelKind.SEGMENT_ORIGINS,
                data=assemble_rows(
                    names=segment_names,
                    positions=origin_positions,
                    columns=SEGMENT_ORIGINS_COLUMNS,
                ),
            ),
        ]
        for kind, source in (
            (ChannelKind.ROTATIONS_LOCAL, message.segment_rotations_local),
            (ChannelKind.ROTATIONS_WORLD, message.segment_rotations_world),
        ):
            quats: dict[str, np.ndarray] = source or {}
            blocks.append(
                SampleBlock(
                    kind=kind,
                    data=assemble_rows(
                        names=segment_names,
                        positions=quats,
                        columns=ROTATION_COLUMNS,
                    ),
                )
            )
        blocks.append(
            SampleBlock(
                kind=ChannelKind.SEGMENT_LENGTHS,
                data=assemble_rows(
                    names=segment_names,
                    positions=lengths,
                    columns=SEGMENT_LENGTHS_COLUMNS,
                ),
            )
        )
        return blocks
