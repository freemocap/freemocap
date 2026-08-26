"""DerivedProducer — whole-body kinematics (center of mass + XCoM).

Active while a realtime pipeline is live. Fills DERIVED_POINTS (two rows:
center_of_mass, xcom). The aggregator already computed CoM / XCoM; the producer
only places them.
"""
from __future__ import annotations


import numpy as np

from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle
from freemocap.core.streaming.message_model import ChannelBlock, ChannelKind
from freemocap.core.streaming.producers.channel_producer import ChannelProducer
from freemocap.core.streaming.producers.producer_contexts import FrameContext, StreamContext

_DERIVED_POINT_NAMES = ("center_of_mass", "xcom")


class DerivedProducer(ChannelProducer):
    def is_active(self, ctx: StreamContext) -> bool:
        return ctx.pipeline_live

    def fill(
        self, frame_ctx: FrameContext, skeleton: TrackedSkeletonBundle
    ) -> list[ChannelBlock]:
        message = frame_ctx.aggregator_output
        if message is None:
            return []
        reconstruction = message.reconstructions.get(skeleton.model_id)
        if reconstruction is None:
            return []
        com_row = np.full(3, np.nan, dtype=np.float32)
        if reconstruction.center_of_mass is not None and not np.any(
            np.isnan(reconstruction.center_of_mass)
        ):
            com_row = np.asarray(reconstruction.center_of_mass, dtype=np.float32)
        xcom_row = np.full(3, np.nan, dtype=np.float32)
        if reconstruction.extrapolated_center_of_mass is not None:
            xcom_row = np.asarray(
                reconstruction.extrapolated_center_of_mass, dtype=np.float32
            )
        derived = np.stack([com_row, xcom_row])
        return [
            ChannelBlock(
                kind=ChannelKind.DERIVED_POINTS,
                names=_DERIVED_POINT_NAMES,
                columns=("x", "y", "z"),
                data=derived.tobytes(order="C"),
            )
        ]
