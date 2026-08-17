"""Compose the self-describing frame message from the channel producers.

One frame message per frame, fully self-contained: the coordinate convention,
the calibrated cameras, the model definitions, the per-frame model instances,
the tracker observations, and the image. The convention + cameras + models are
composed once per data model (from the StreamContext); the instances + trackers
+ image are composed per frame from the active producers.

Channel routing is by kind: KEYPOINTS_3D / OVERLAY_2D are tracker keypoint
observations (routed to trackers); everything else is model reconstruction
(routed to instances).
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from freemocap.core.streaming.message_model import (
    CalibratedCamera,
    ChannelKind,
    CoordinateConvention,
    FrameMessage,
    MessageEnvelope,
    ModelDefinition,
    ModelInstance,
    TrackerObservation,
)
from freemocap.core.streaming.producers import ALL_PRODUCERS
from freemocap.core.streaming.producers.producer_contexts import FrameContext, StreamContext

_TRACKER_KINDS = frozenset((ChannelKind.KEYPOINTS_3D, ChannelKind.OVERLAY_2D))


@dataclass(frozen=True, slots=True)
class MessageComposition:
    """One stream data model's static message parts + the frame-building context."""

    context: StreamContext
    producers: tuple
    convention: CoordinateConvention
    cameras: tuple[CalibratedCamera, ...]
    models: tuple[ModelDefinition, ...]
    model_sequence: int = 0

    def compose_frame_message(self, frame_ctx: FrameContext) -> FrameMessage:
        fill_ctx = replace(frame_ctx, stream_context=self.context)
        blocks = tuple(block for producer in self.producers for block in producer.fill(fill_ctx))
        instance_blocks = tuple(b for b in blocks if b.kind not in _TRACKER_KINDS)
        tracker_blocks = tuple(b for b in blocks if b.kind in _TRACKER_KINDS)
        instances = (
            ModelInstance(instance_id=0, model_id="standard_human", channels=instance_blocks),
        ) if instance_blocks else ()
        trackers = (
            TrackerObservation(
                tracker_id=self.context.detector_type,
                detector_type=self.context.detector_type,
                model_id="standard_human",
                channels=tracker_blocks,
            ),
        ) if tracker_blocks else ()
        return FrameMessage(
            envelope=MessageEnvelope(
                timestamp=float(frame_ctx.timestamp),
                sequence=int(frame_ctx.frame_number),
            ),
            frame_number=int(frame_ctx.frame_number),
            model_sequence=self.model_sequence,
            convention=self.convention,
            cameras=self.cameras,
            models=self.models,
            instances=instances,
            trackers=trackers,
            image=frame_ctx.image_payload,
        )


def compose_messages(ctx: StreamContext) -> MessageComposition:
    """Build the static message parts for the current data model."""
    active = tuple(producer for producer in ALL_PRODUCERS if producer.is_active(ctx))
    return MessageComposition(
        context=ctx,
        producers=active,
        convention=CoordinateConvention(),
        cameras=ctx.calibrated_cameras,
        models=(ModelDefinition.from_standard_human(ctx.standard_human),),
    )
