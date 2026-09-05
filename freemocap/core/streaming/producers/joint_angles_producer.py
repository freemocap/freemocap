"""JointAnglesProducer — the linkage layer's named joint angles.

Active while a realtime pipeline is live. Fills JOINT_ANGLES: one row per
joint, one radians column per row, named ``<joint>.<angle_name>`` inline so the
channel is self-describing without a model-definition round trip. The
aggregator already computed the angles (skellyforge's ``compute_joint_poses``
over the backfilled pose); this producer only places them.
"""
from __future__ import annotations


import numpy as np

from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle
from freemocap.core.streaming.message_model import ChannelBlock, ChannelKind
from freemocap.core.streaming.producers.channel_producer import ChannelProducer
from freemocap.core.streaming.producers.producer_contexts import FrameContext, StreamContext


class JointAnglesProducer(ChannelProducer):
    def is_active(self, ctx: StreamContext) -> bool:
        return ctx.pipeline_live

    def fill(
        self, frame_ctx: FrameContext, skeleton: TrackedSkeletonBundle
    ) -> list[ChannelBlock]:
        message = frame_ctx.aggregator_output
        if message is None:
            return []
        reconstruction = message.reconstructions.get(skeleton.model_id)
        # A skeleton with no joints — a rigid marked object — has no angles, and that is
        # an absent channel rather than a channel of NaNs.
        if reconstruction is None or not reconstruction.joint_angles:
            return []

        names: list[str] = []
        values: list[float] = []
        for joint_name, angles in sorted(reconstruction.joint_angles.items()):
            for angle_index, name in enumerate(skeleton.skeleton.joints[joint_name].angle_names):
                names.append(name)
                value = float(angles[angle_index])
                values.append(value if np.isfinite(value) else np.nan)

        column = np.asarray(values, dtype=np.float32)
        return [
            ChannelBlock(
                kind=ChannelKind.JOINT_ANGLES,
                names=tuple(names),
                columns=("radians",),
                data=column.tobytes(order="C"),
            )
        ]
