"""Compose the self-describing frame message from the channel producers.

One frame message per frame, fully self-contained: the coordinate convention,
the calibrated cameras, the model definitions, the per-frame model instances,
the tracker observations, and the image. The convention + cameras + models are
composed once per data model (from the StreamContext); the instances + trackers
+ image are composed per frame from the active producers.

Channel routing is by kind: KEYPOINTS_3D / OVERLAY_2D / BOXES_2D are tracker
observations (routed to trackers); everything else is model reconstruction
(routed to instances).
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from skellytracker.core.io.tracker_profiles import hand_connections
import numpy as np
from freemocap.core.diagnostics.pipeline_diagnostics import frame_diagnostics

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
from freemocap.core.streaming.producers.overlay_producer import OverlayProducer
from freemocap.core.streaming.rest_geometry import ModelConnectionGroup
from freemocap.core.streaming.channel_helpers import assemble_channel_bytes, temporal_status_bytes, TEMPORAL_STATUS_LABELS
from freemocap.core.streaming.message_model import ChannelBlock

_TRACKER_KINDS = frozenset(
    (ChannelKind.KEYPOINTS_3D, ChannelKind.OVERLAY_2D, ChannelKind.BOXES_2D)
)
_OVERLAY_PRODUCER = OverlayProducer()


@lru_cache(maxsize=1)
def _hand_connections():
    return (ModelConnectionGroup(name="hand", pairs=hand_connections(), color="#00AA00"),)


@dataclass(frozen=True, slots=True)
class MessageComposition:
    """One stream data model's static message parts + the frame-building context."""

    context: StreamContext
    producers: tuple[ChannelProducer, ...]
    convention: CoordinateConvention
    cameras: tuple[CalibratedCamera, ...]
    models: tuple[ModelDefinition, ...]
    independent_connections: tuple[tuple[ModelConnectionGroup, ...], ...] = ()
    model_sequence: int = 0

    def compose_frame_message(self, frame_ctx: FrameContext) -> FrameMessage:
        fill_ctx = replace(frame_ctx, stream_context=self.context)
        instances: list[ModelInstance] = []
        trackers: list[TrackerObservation] = []
        # One instance and one tracker observation PER SKELETON. A session tracking a
        # person and a charuco board emits two of each; the producers were called with
        # each skeleton in turn, so no block can land under the wrong model.
        aggregation = frame_ctx.aggregator_output
        subjects = []
        for index, skeleton in enumerate(self.context.skeletons):
            if skeleton.detector_type == "mediapipe_hands":
                for hand in aggregation.hand_observations if aggregation is not None else ():
                    if hand.model_id == skeleton.model_id:
                        subjects.append((hand.track_id, skeleton, replace(fill_ctx, hand=hand)))
            else:
                subjects.append((index, skeleton, fill_ctx))
        for instance_id, skeleton, subject_ctx in subjects:
            hand = subject_ctx.hand
            blocks = tuple(
                block
                for producer in self.producers
                for block in producer.fill(subject_ctx, skeleton)
            )
            instance_blocks = tuple(b for b in blocks if b.kind not in _TRACKER_KINDS)
            tracker_blocks = tuple(b for b in blocks if b.kind in _TRACKER_KINDS)
            reconstruction = subject_ctx.reconstruction_for(skeleton)
            if reconstruction is not None and reconstruction.generated_support:
                from freemocap.core.streaming.channel_helpers import TEMPORAL_STATUS_LABELS
                # Derived channels must not lose their dependence on generated poses.
                instance_blocks = tuple(replace(block,
                    sample_status=(np.isfinite(np.frombuffer(block.data, dtype='<f4').reshape(-1, len(block.columns))).any(axis=-1).astype(np.uint8) * 2).tobytes(),
                    status_labels=TEMPORAL_STATUS_LABELS) if block.sample_status is None else block
                    for block in instance_blocks)
            if instance_blocks and (hand is None or reconstruction is not None):
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
                        tracker_id=skeleton.detector_type if hand is None else hand.tracker_id,
                        handedness=hand.handedness if hand else None,
                        connection_groups=_hand_connections() if hand else (),
                        detector_type=skeleton.detector_type,
                        model_id=skeleton.model_id,
                        channels=tracker_blocks,
                    )
                )
        if self.context.pipeline_live:
            for metadata, connections in zip(
                self.context.independent_trackers, self.independent_connections, strict=True,
            ):
                if any(skeleton.detector_type == "dlc" for skeleton in self.context.skeletons):
                    continue
                channels = list(_OVERLAY_PRODUCER.fill_tracker(fill_ctx, metadata))
                # Model-only detector outputs need no anatomical definition. Publish
                # metric points only when multicamera calibration actually applies.
                if (aggregation is not None and aggregation.calibration_applicable
                        and len(aggregation.camera_node_outputs) > 1
                        and aggregation.keypoints_arrays is not None):
                    names = metadata.keypoint_names
                    channels.append(ChannelBlock(
                        kind=ChannelKind.KEYPOINTS_3D, names=names, columns=("x", "y", "z"),
                        data=assemble_channel_bytes(names=names, positions=aggregation.keypoints_arrays,
                                                    columns=("x", "y", "z")),
                        sample_status=temporal_status_bytes(names=names, status=aggregation.keypoint_status),
                        status_labels=TEMPORAL_STATUS_LABELS if aggregation.keypoint_status is not None else None,
                    ))
                trackers.append(TrackerObservation(
                    tracker_id=metadata.model_sha256, detector_type="dlc", model_id=None,
                    channels=tuple(channels),
                    connection_groups=connections,
                ))
        diagnostics = frame_diagnostics(
            reprojection=aggregation.reprojection_diagnostics,
            reconstructions=aggregation.reconstructions,
            length_units='millimeters' if aggregation.calibration_applicable and len(aggregation.camera_node_outputs) > 1 else 'pixels',
        ) if aggregation is not None else None
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
            diagnostics=diagnostics,
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
        independent_connections=tuple(
            tuple(ModelConnectionGroup(name=name, pairs=edges, color="#00AA00")
                  for name, edges in metadata.connection_groups)
            for metadata in ctx.independent_trackers
        ),
        # One definition per tracked skeleton. Colours are resolved from each skeleton's
        # group tags HERE, so the wire carries an answer and no client needs the palette.
        models=tuple(
            ModelDefinition.from_skeleton(
                model_id=skeleton.model_id,
                skeleton=skeleton.skeleton,
                rest_pose=skeleton.rest_pose,
                palette=palette,
                scale_reference_name=skeleton.scale_reference_name,
                tracker_connections=skeleton.tracker_connections,
                object_geometry=skeleton.object_geometry,
            )
            for skeleton in ctx.skeletons
        ),
    )
