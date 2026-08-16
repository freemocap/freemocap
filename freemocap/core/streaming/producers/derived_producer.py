"""DerivedProducer — whole-body kinematics (center of mass + XCoM).

Active while a realtime pipeline is live. Fills DERIVED_POINTS (two rows:
center_of_mass, xcom). The aggregator already computed CoM / XCoM; the producer
only places them.
"""
from __future__ import annotations

from collections.abc import Hashable

import numpy as np

from freemocap.core.streaming.message_model import ChannelBlock, ChannelKind
from freemocap.core.streaming.producers.channel_producer import ChannelProducer
from freemocap.core.streaming.producers.producer_contexts import FrameContext, StreamContext

_DERIVED_POINT_NAMES = ("center_of_mass", "xcom")


class DerivedProducer(ChannelProducer):
    def is_active(self, ctx: StreamContext) -> bool:
        return ctx.pipeline_live

    def signature(self, ctx: StreamContext) -> Hashable:
        return ("derived",)

    def fill(self, frame_ctx: FrameContext) -> list[ChannelBlock]:
        message = frame_ctx.aggregator_output
        if message is None:
            return []
        com_row = np.full(3, np.nan, dtype=np.float32)
        if message.center_of_mass_result is not None and not np.any(
            np.isnan(message.center_of_mass_result.total_body_com)
        ):
            com_row = message.center_of_mass_result.total_body_com.astype(np.float32)
        xcom_row = np.full(3, np.nan, dtype=np.float32)
        if message.xcom is not None:
            xcom_row = np.array([message.xcom.x, message.xcom.y, message.xcom.z], dtype=np.float32)
        derived = np.stack([com_row, xcom_row])
        return [
            ChannelBlock(
                kind=ChannelKind.DERIVED_POINTS,
                names=_DERIVED_POINT_NAMES,
                columns=("x", "y", "z"),
                data=derived.tobytes(order="C"),
            )
        ]
