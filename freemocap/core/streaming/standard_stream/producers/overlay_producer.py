"""OverlayProducer — the per-camera 2D overlays.

Active while a realtime pipeline is live. Contributes ``OVERLAY_2D`` (one
DETECTIONS block per camera per frame — the tracker's raw 2D keypoints, values
in capture-resolution image px) and ``OVERLAY_REPROJECTIONS`` (one block per
camera per frame — the fitted skeleton's segment-origin landmarks projected
back into the camera; NaN rows when there is no valid calibration / no solve
this frame). The schema's ``camera_image_sizes`` declares each camera's
coordinate space.
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
    camera_2d_detections,
)
from freemocap.core.streaming.standard_stream.stream_sample import SampleBlock
from freemocap.core.streaming.standard_stream.stream_schema import (
    OVERLAY_2D_COLUMNS,
    ChannelGroup,
    ChannelKind,
    OverlayLayer,
)


class OverlayProducer(ChannelProducer):
    def is_active(self, ctx: StreamContext) -> bool:
        return ctx.pipeline_live

    def schema_groups(self, ctx: StreamContext) -> list[ChannelGroup]:
        return [
            ChannelGroup(
                kind=ChannelKind.OVERLAY_2D,
                names=tuple(ctx.tracker_keypoint_names),
                columns=OVERLAY_2D_COLUMNS,
                units="px",
            ),
            ChannelGroup(
                kind=ChannelKind.OVERLAY_REPROJECTIONS,
                names=tuple(ctx.standard_human.segment_names),
                columns=OVERLAY_2D_COLUMNS,
                units="px",
            ),
        ]

    def schema_metadata(self, ctx: StreamContext) -> dict[str, object]:
        return {}

    def signature(self, ctx: StreamContext) -> Hashable:
        return ("overlay", tuple(sorted(ctx.camera_ids)))

    def fill(self, frame_ctx: FrameContext) -> list[SampleBlock]:
        message = frame_ctx.aggregator_output
        stream_ctx = frame_ctx.stream_context
        if message is None or stream_ctx is None:
            return []
        kp_names = tuple(stream_ctx.tracker_keypoint_names)
        segment_names = tuple(stream_ctx.standard_human.segment_names)
        blocks: list[SampleBlock] = []
        for camera_id in stream_ctx.camera_ids:
            detections = camera_2d_detections(message, camera_id)
            blocks.append(
                SampleBlock(
                    kind=ChannelKind.OVERLAY_2D,
                    data=assemble_rows(
                        names=kp_names,
                        positions=detections,
                        columns=OVERLAY_2D_COLUMNS,
                    ),
                    camera_id=camera_id,
                    overlay_layer=OverlayLayer.DETECTIONS,
                )
            )
            reprojections = {
                name: np.asarray(xy, dtype=np.float32)
                for name, xy in message.reprojected_segment_origins.get(camera_id, {}).items()
            }
            blocks.append(
                SampleBlock(
                    kind=ChannelKind.OVERLAY_REPROJECTIONS,
                    data=assemble_rows(
                        names=segment_names,
                        positions=reprojections,
                        columns=OVERLAY_2D_COLUMNS,
                    ),
                    camera_id=camera_id,
                    overlay_layer=OverlayLayer.REPROJECTIONS,
                )
            )
        return blocks

