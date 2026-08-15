"""KeypointsProducer — the measured keypoints + hydrated landmarks.

Active while a realtime pipeline is live. Contributes the dual point channels:
``KEYPOINTS_3D`` (tracker-named measured keypoints from
``message.keypoints_arrays``) and ``LANDMARKS_3D`` (the 76 hydrated
standard-human landmarks from ``message.standard_skeleton``). A missing point
is a NaN row — never a dropped block.
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
)
from freemocap.core.streaming.standard_stream.stream_sample import SampleBlock
from freemocap.core.streaming.standard_stream.stream_schema import (
    KEYPOINTS_3D_COLUMNS,
    ChannelGroup,
    ChannelKind,
)


class KeypointsProducer(ChannelProducer):
    def is_active(self, ctx: StreamContext) -> bool:
        return ctx.pipeline_live

    def schema_groups(self, ctx: StreamContext) -> list[ChannelGroup]:
        units = ctx.convention.units.value
        return [
            ChannelGroup(
                kind=ChannelKind.KEYPOINTS_3D,
                names=tuple(ctx.tracker_keypoint_names),
                columns=KEYPOINTS_3D_COLUMNS,
                units=units,
            ),
            ChannelGroup(
                kind=ChannelKind.LANDMARKS_3D,
                names=tuple(sorted(ctx.standard_human.required_landmarks())),
                columns=KEYPOINTS_3D_COLUMNS,
                units=units,
            ),
        ]

    def schema_metadata(self, ctx: StreamContext) -> dict[str, object]:
        return {}

    def signature(self, ctx: StreamContext) -> Hashable:
        return ("keypoints", tuple(ctx.tracker_keypoint_names))

    def fill(self, frame_ctx: FrameContext) -> list[SampleBlock]:
        message = frame_ctx.aggregator_output
        stream_ctx = frame_ctx.stream_context
        if message is None or stream_ctx is None:
            return []
        tracker_positions: dict[str, np.ndarray] = message.keypoints_arrays or {}
        positions: dict[str, np.ndarray] = message.standard_skeleton or {}
        return [
            SampleBlock(
                kind=ChannelKind.KEYPOINTS_3D,
                data=assemble_rows(
                    names=tuple(stream_ctx.tracker_keypoint_names),
                    positions=tracker_positions,
                    columns=KEYPOINTS_3D_COLUMNS,
                ),
            ),
            SampleBlock(
                kind=ChannelKind.LANDMARKS_3D,
                data=assemble_rows(
                    names=tuple(sorted(stream_ctx.standard_human.required_landmarks())),
                    positions=positions,
                    columns=KEYPOINTS_3D_COLUMNS,
                ),
            ),
        ]
