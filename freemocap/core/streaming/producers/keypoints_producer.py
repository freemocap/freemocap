"""KeypointsProducer — the measured keypoints + hydrated landmarks.

Active while a realtime pipeline is live. Fills KEYPOINTS_3D (tracker-named
measured keypoints) and LANDMARKS_3D (the hydrated standard-human landmarks)
as self-describing ChannelBlocks. A missing point is a NaN row — never a
dropped block.
"""
from __future__ import annotations


from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle
from freemocap.core.streaming.channel_helpers import assemble_channel_bytes
from freemocap.core.streaming.message_model import ChannelBlock, ChannelKind
from freemocap.core.streaming.producers.channel_producer import ChannelProducer
from freemocap.core.streaming.producers.producer_contexts import FrameContext, StreamContext


class KeypointsProducer(ChannelProducer):
    def is_active(self, ctx: StreamContext) -> bool:
        return ctx.pipeline_live

    def fill(
        self, frame_ctx: FrameContext, skeleton: TrackedSkeletonBundle
    ) -> list[ChannelBlock]:
        message = frame_ctx.aggregator_output
        if message is None:
            return []
        # Each skeleton's own detector names its keypoints, so a charuco board's corners
        # ride its tracker observation and a pose detector's joints ride the human's.
        tracker_names = tuple(skeleton.tracker_keypoint_names)
        landmark_names = tuple(skeleton.skeleton.landmarks)
        reconstruction = message.reconstructions.get(skeleton.model_id)
        return [
            ChannelBlock(
                kind=ChannelKind.KEYPOINTS_3D,
                names=tracker_names,
                columns=("x", "y", "z", "reprojection_error"),
                data=assemble_channel_bytes(names=tracker_names, positions=message.keypoints_arrays or {}, n_cols=4),
            ),
            ChannelBlock(
                kind=ChannelKind.LANDMARKS_3D,
                columns=("x", "y", "z", "reprojection_error"),
                data=assemble_channel_bytes(
                    names=landmark_names,
                    positions=reconstruction.landmarks if reconstruction else {},
                    n_cols=4,
                ),
            ),
        ]
