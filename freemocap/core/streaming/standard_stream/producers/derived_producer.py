"""DerivedProducer — whole-body kinematics (center of mass + XCoM).

Active while a realtime pipeline is live. Contributes ``DERIVED_POINTS``
(rows keyed by schema-declared name — never by positional index — so a
reordering of the derived channels never misplaces a row). The aggregator
already computed CoM / XCoM; the producer only places them.
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
from freemocap.core.streaming.standard_stream.stream_sample import SampleBlock
from freemocap.core.streaming.standard_stream.stream_schema import (
    DEFAULT_DERIVED_POINTS,
    DERIVED_POINT_COLUMNS,
    ChannelGroup,
    ChannelKind,
)


class DerivedProducer(ChannelProducer):
    def is_active(self, ctx: StreamContext) -> bool:
        return ctx.pipeline_live

    def schema_groups(self, ctx: StreamContext) -> list[ChannelGroup]:
        return [
            ChannelGroup(
                kind=ChannelKind.DERIVED_POINTS,
                names=DEFAULT_DERIVED_POINTS,
                columns=DERIVED_POINT_COLUMNS,
                units=ctx.convention.units.value,
            ),
        ]

    def schema_metadata(self, ctx: StreamContext) -> dict[str, object]:
        return {}

    def signature(self, ctx: StreamContext) -> Hashable:
        return ("derived",)

    def fill(self, frame_ctx: FrameContext) -> list[SampleBlock]:
        message = frame_ctx.aggregator_output
        if message is None:
            return []

        com_row = np.full(3, np.nan)
        if message.center_of_mass_result is not None and not np.any(
            np.isnan(message.center_of_mass_result.total_body_com)
        ):
            com_row = message.center_of_mass_result.total_body_com.astype(np.float32)
        xcom_row = np.full(3, np.nan)
        if message.xcom is not None:
            xcom_row = np.array(
                [message.xcom.x, message.xcom.y, message.xcom.z], dtype=np.float32
            )
        derived_by_name = {
            "center_of_mass": com_row,
            "xcom": xcom_row,
        }
        derived_data = np.stack([derived_by_name[n] for n in DEFAULT_DERIVED_POINTS])
        return [
            SampleBlock(
                kind=ChannelKind.DERIVED_POINTS,
                data=derived_data.astype(np.float32),
            )
        ]
