"""BoxProducer — the per-camera 2D bounding boxes.

Active while a realtime pipeline is live. Fills BOXES_2D: one block per camera
holding each detection stage's box as (x1, y1, x2, y2, confidence, detector_ran).

These boxes are what the keypoint detector actually gets cropped to, so drawing
them is the only way an over-eager re-detect or a collapsed crop is visible
without reading a timing report. A stage with no box this frame is a NaN row —
never a dropped block.
"""
from __future__ import annotations


from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle
from freemocap.core.streaming.channel_helpers import (
    assemble_channel_bytes,
    camera_2d_boxes,
    detector_produces_boxes,
    detector_stage_names,
)
from freemocap.core.streaming.message_model import ChannelBlock, ChannelKind
from freemocap.core.streaming.producers.channel_producer import ChannelProducer
from freemocap.core.streaming.producers.producer_contexts import FrameContext, StreamContext

BOX_COLUMNS: tuple[str, ...] = (
    "x1", "y1", "x2", "y2", "confidence", "detector_ran",
)


class BoxProducer(ChannelProducer):
    def is_active(self, ctx: StreamContext) -> bool:
        return ctx.pipeline_live

    def fill(
        self, frame_ctx: FrameContext, skeleton: TrackedSkeletonBundle
    ) -> list[ChannelBlock]:
        message = frame_ctx.aggregator_output
        stream_ctx = frame_ctx.stream_context
        if message is None or stream_ctx is None:
            return []
        # A detector with no object detector (charuco, mediapipe) has its crop
        # synthesized as the whole frame, so it has no box worth a channel — drawing a
        # rectangle around the entire image on every camera tells the viewer nothing.
        if not detector_produces_boxes(skeleton.detector_type):
            return []
        stage_names = detector_stage_names(skeleton.detector_type)
        blocks: list[ChannelBlock] = []
        for camera_id in stream_ctx.camera_ids:
            boxes = camera_2d_boxes(
                message, camera_id, detector_type=skeleton.detector_type
            )
            blocks.append(
                ChannelBlock(
                    kind=ChannelKind.BOXES_2D,
                    names=stage_names,
                    columns=BOX_COLUMNS,
                    data=assemble_channel_bytes(
                        names=stage_names, positions=boxes, n_cols=len(BOX_COLUMNS),
                    ),
                    camera_id=camera_id,
                    image_size=stream_ctx.live_image_sizes.get(camera_id),
                )
            )
        return blocks
