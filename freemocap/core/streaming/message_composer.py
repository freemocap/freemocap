"""Compose self-describing messages from the channel producers.

Bridges the channel producers (fill -> ChannelBlock) to the message-model
dataclasses. One message set per stream data model: three replace-kinds
(convention, model, camera_layout) emitted on connect and re-emitted whole when
the signature changes, plus a self-describing frame message per frame.

See current-work-plans/03-transport/message-relay.md.
"""
from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass, replace

from freemocap.core.streaming.message_model import (
    CameraLayoutMessage,
    ConventionMessage,
    FrameMessage,
    ModelMessage,
    Subject,
)
from freemocap.core.streaming.producers import ALL_PRODUCERS, signature_of
from freemocap.core.streaming.producers.producer_contexts import FrameContext, StreamContext


@dataclass(frozen=True, slots=True)
class MessageComposition:
    """One stream data model's message set + the frame-building context."""

    context: StreamContext
    producers: tuple
    convention: ConventionMessage
    model: ModelMessage
    camera_layout: CameraLayoutMessage

    @property
    def signature(self) -> Hashable:
        return signature_of(self.context)

    def compose_frame_message(self, frame_ctx: FrameContext) -> FrameMessage:
        fill_ctx = replace(frame_ctx, stream_context=self.context)
        channels = tuple(
            block for producer in self.producers for block in producer.fill(fill_ctx)
        )
        return FrameMessage(
            frame_number=int(frame_ctx.frame_number),
            timestamp=float(frame_ctx.timestamp),
            subjects=(Subject(subject_id=0, channels=channels),),
            image=frame_ctx.image_payload,
        )


def compose_messages(ctx: StreamContext) -> MessageComposition:
    """Build the message set for the current data model from the active producers."""
    active = tuple(producer for producer in ALL_PRODUCERS if producer.is_active(ctx))
    return MessageComposition(
        context=ctx,
        producers=active,
        convention=ConventionMessage(),
        model=ModelMessage.from_standard_human(ctx.standard_human),
        camera_layout=CameraLayoutMessage(
            camera_ids=tuple(ctx.camera_ids),
            image_sizes=dict(ctx.camera_image_sizes),
        ),
    )
