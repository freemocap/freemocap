"""OverlayProducer — the per-camera 2D overlays.

Active while a realtime pipeline is live. Fills OVERLAY_2D (tracker keypoint
detections) and OVERLAY_REPROJECTIONS (the fitted skeleton's segment-origin
landmarks projected back into the camera) — one block per camera.
"""
from __future__ import annotations

from collections.abc import Hashable

import numpy as np

from freemocap.core.streaming.channel_helpers import assemble_channel_bytes, camera_2d_detections
from freemocap.core.streaming.message_model import ChannelBlock, ChannelKind
from freemocap.core.streaming.producers.channel_producer import ChannelProducer
from freemocap.core.streaming.producers.producer_contexts import FrameContext, StreamContext


class OverlayProducer(ChannelProducer):
    def is_active(self, ctx: StreamContext) -> bool:
        return ctx.pipeline_live

    def signature(self, ctx: StreamContext) -> Hashable:
        return ("overlay", tuple(sorted(ctx.camera_ids)))

    def fill(self, frame_ctx: FrameContext) -> list[ChannelBlock]:
        message = frame_ctx.aggregator_output
        stream_ctx = frame_ctx.stream_context
        if message is None or stream_ctx is None:
            return []
        kp_names = tuple(stream_ctx.tracker_keypoint_names)
        segment_names = tuple(stream_ctx.standard_human.segment_names)
        blocks: list[ChannelBlock] = []
        for camera_id in stream_ctx.camera_ids:
            detections = camera_2d_detections(message, camera_id)
            blocks.append(
                ChannelBlock(
                    kind=ChannelKind.OVERLAY_2D,
                    names=kp_names,
                    columns=("x", "y", "visibility"),
                    data=assemble_channel_bytes(names=kp_names, positions=detections, n_cols=3),
                    camera_id=camera_id,
                )
            )
            reprojections = {
                name: np.asarray(xy, dtype=np.float32)
                for name, xy in message.reprojected_segment_origins.get(camera_id, {}).items()
            }
            blocks.append(
                ChannelBlock(
                    kind=ChannelKind.OVERLAY_REPROJECTIONS,
                    names=segment_names,
                    columns=("x", "y", "visibility"),
                    data=assemble_channel_bytes(names=segment_names, positions=reprojections, n_cols=3),
                    camera_id=camera_id,
                )
            )
        return blocks
