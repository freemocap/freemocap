"""JointAnglesProducer — the linkage layer's named joint angles.

Active while a realtime pipeline is live. Fills JOINT_ANGLES: one row per
joint, one radians column per row, named ``<joint>.<angle_name>`` inline so the
channel is self-describing without a model-definition round trip. The
aggregator already computed the angles (skellyforge's ``compute_joint_poses``
over the backfilled pose); this producer only places them.
"""
from __future__ import annotations


import numpy as np
from skellyforge.core.data_tensors.channel_values import ChannelValues
from freemocap.core.skeletons.skeleton_reconstruction import JointValues

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

        joint_names = tuple(skeleton.skeleton.joints)
        names = tuple(name for joint in skeleton.skeleton.joints.values() for name in joint.angle_names)
        unknown_joints = set(reconstruction.joint_angles) - set(joint_names)
        if unknown_joints:
            raise ValueError(f"Undeclared joint identities: {unknown_joints}")
        if isinstance(reconstruction.joint_angles, JointValues):
            values = reconstruction.joint_angles.angle_values.aligned(names).reshape(-1)
        elif isinstance(reconstruction.joint_angles, ChannelValues):
            values = reconstruction.joint_angles.aligned(joint_names).reshape(-1)
        else:
            # External named fixtures enter once; production publishes dense joint arrays.
            rows = []
            for name, definition in skeleton.skeleton.joints.items():
                row = reconstruction.joint_angles.get(name)
                if row is None:
                    row = np.full(len(definition.angle_names), np.nan)
                if len(row) != len(definition.angle_names):
                    raise ValueError(f"Joint {name} values do not match its declared angles")
                rows.append(row)
            values = np.concatenate(rows)
        if values.size != len(names):
            raise ValueError("Joint values do not match declared angle identities")
        column = np.asarray(values, dtype='<f4')
        return [
            ChannelBlock(
                kind=ChannelKind.JOINT_ANGLES,
                names=tuple(names),
                columns=("radians",),
                data=column.tobytes(order="C"),
            )
        ]
