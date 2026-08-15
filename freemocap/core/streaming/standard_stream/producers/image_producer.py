"""ImageProducer — the camera images as an ``IMAGE_JPEG`` channel group.

Active whenever cameras exist (every mode). One opaque block per frame carries
the SkellyCam multi-camera frontend payload (display-size JPEGs for all
cameras); the consumer's frame decoder splits it per camera. The schema's
``camera_image_sizes`` (the OVERLAY_2D coordinate space) is this producer's
metadata.
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
    IMAGE_JPEG_COLUMNS,
    ChannelGroup,
    ChannelKind,
)

IMAGE_JPEG_NAMES: tuple[str, ...] = ("image",)


class ImageProducer(ChannelProducer):
    def is_active(self, ctx: StreamContext) -> bool:
        return bool(ctx.camera_ids)

    def schema_groups(self, ctx: StreamContext) -> list[ChannelGroup]:
        return [
            ChannelGroup(
                kind=ChannelKind.IMAGE_JPEG,
                names=IMAGE_JPEG_NAMES,
                columns=IMAGE_JPEG_COLUMNS,
                units="jpeg",
            ),
        ]

    def schema_metadata(self, ctx: StreamContext) -> dict[str, object]:
        return {
            "camera_ids": ctx.camera_ids,
            "camera_image_sizes": dict(ctx.camera_image_sizes),
        }

    def signature(self, ctx: StreamContext) -> Hashable:
        # The image sizes ride the signature: a camera rotation change keeps
        # the same camera ids but swaps width/height — the schema must re-send
        # so consumers re-scale their overlays without any restart.
        return (
            "image",
            tuple(sorted(ctx.camera_ids)),
            tuple(sorted(ctx.camera_image_sizes.items())),
        )

    def fill(self, frame_ctx: FrameContext) -> list[SampleBlock]:
        if frame_ctx.image_payload is None:
            return []
        data = np.frombuffer(frame_ctx.image_payload, dtype=np.uint8).reshape(-1, 1)
        return [SampleBlock(kind=ChannelKind.IMAGE_JPEG, data=data)]
