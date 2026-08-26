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
from skellyforge.core.skeleton.components.color_palette import ColorPalette

from freemocap.core.streaming.producers import ALL_PRODUCERS
from freemocap.core.streaming.producers.channel_producer import ChannelProducer
from freemocap.core.streaming.producers.producer_contexts import FrameContext, StreamContext

_TRACKER_KINDS = frozenset((ChannelKind.KEYPOINTS_3D, ChannelKind.OVERLAY_2D))


@dataclass(frozen=True, slots=True)
class MessageComposition:
    """One stream data model's static message parts + the frame-building context."""

    context: StreamContext
    producers: tuple[ChannelProducer, ...]
    convention: CoordinateConvention
    cameras: tuple[CalibratedCamera, ...]
    models: tuple[ModelDefinition, ...]
    model_sequence: int = 0

    def compose_frame_message(self, frame_ctx: FrameContext) -> FrameMessage:
        fill_ctx = replace(frame_ctx, stream_context=self.context)
        reconstructions = (
            frame_ctx.aggregator_output.reconstructions
            if frame_ctx.aggregator_output is not None
            else {}
        )
        instances: list[ModelInstance] = []
        trackers: list[TrackerObservation] = []
        # One instance and one tracker observation PER SKELETON. A session tracking a
        # person and a charuco board emits two of each; the producers were called with
        # each skeleton in turn, so no block can land under the wrong model.
        for instance_id, skeleton in enumerate(self.context.skeletons):
            blocks = tuple(
                block
                for producer in self.producers
                for block in producer.fill(fill_ctx, skeleton)
            )
            instance_blocks = tuple(b for b in blocks if b.kind not in _TRACKER_KINDS)
            tracker_blocks = tuple(b for b in blocks if b.kind in _TRACKER_KINDS)
            reconstruction = reconstructions.get(skeleton.model_id)
            if instance_blocks:
                instances.append(
                    ModelInstance(
                        instance_id=instance_id,
                        model_id=skeleton.model_id,
                        channels=instance_blocks,
                        fitted_scale_mm=(
                            reconstruction.fitted_scale_mm if reconstruction else None
                        ),
                    )
                )
            if tracker_blocks:
                trackers.append(
                    TrackerObservation(
                        tracker_id=skeleton.detector_type,
                        detector_type=skeleton.detector_type,
                        model_id=skeleton.model_id,
                        channels=tracker_blocks,
                    )
                )
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
            instances=tuple(instances),
            trackers=tuple(trackers),
            image=frame_ctx.image_payload,
        )


def compose_messages(ctx: StreamContext) -> MessageComposition:
    """Build the static message parts for the current data model."""
    active = tuple(producer for producer in ALL_PRODUCERS if producer.is_active(ctx))
    palette = ColorPalette.from_default_yaml()
    return MessageComposition(
        context=ctx,
        producers=active,
        convention=CoordinateConvention(),
        cameras=ctx.calibrated_cameras,
        # One definition per tracked skeleton. Colours are resolved from each skeleton's
        # group tags HERE, so the wire carries an answer and no client needs the palette.
        models=tuple(
            ModelDefinition.from_skeleton(
                model_id=skeleton.model_id,
                skeleton=skeleton.skeleton,
                rest_pose=skeleton.rest_pose,
                palette=palette,
                scale_reference_name=skeleton.scale_reference_name,
            )
            for skeleton in ctx.skeletons
        ),
    )
