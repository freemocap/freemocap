"""
PubSub topic definitions for the pipeline system.

Each Message + Topic pair defines a typed channel. Topics auto-register
via __init_subclass__ so the PubSubTopicManager discovers them at startup.
"""
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString, MultiframeTimestampFloat
from skellyforge.data_models.trajectory_3d import Point3d
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseObservation

from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.tasks.mocap.skeleton_dewiggler.dewiggling_methods.rigid_body_estimator import RigidBodyPose
from freemocap.core.types.type_overloads import (
    FrameNumberInt,
    PipelineIdString,
    TrackedPointNameString,
)
from freemocap.pubsub.pubsub_abcs import TopicMessageABC, create_topic

if TYPE_CHECKING:
    from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation
    from freemocap.core.viz.image_overlay.charuco_overlay_data import CharucoOverlayData
    from freemocap.core.viz.image_overlay.skeleton_overlay_data import SkeletonOverlayData

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Frame processing
# ---------------------------------------------------------------------------

@dataclass
class ProcessFrameNumberMessage(TopicMessageABC):
    frame_number: int = 0

    def __post_init__(self) -> None:
        if self.frame_number < 0:
            raise ValueError(f"frame_number must be >= 0, got {self.frame_number}")


# ---------------------------------------------------------------------------
# Config updates
# ---------------------------------------------------------------------------

@dataclass
class PipelineConfigUpdateMessage(TopicMessageABC):
    pipeline_config: RealtimePipelineConfig = None


# ---------------------------------------------------------------------------
# Realtime node outputs
# ---------------------------------------------------------------------------

@dataclass
class CameraNodeOutputMessage(TopicMessageABC):
    camera_id: CameraIdString = ""
    frame_number: FrameNumberInt = 0
    charuco_observation: BaseObservation | None = None
    skeleton_observation: BaseObservation | None = None

    def __post_init__(self) -> None:
        if self.frame_number < 0:
            raise ValueError(f"frame_number must be >= 0, got {self.frame_number}")


# ---------------------------------------------------------------------------
# Centralized GPU skeleton inference results
# ---------------------------------------------------------------------------
# Published by RealtimeSkeletonInferenceNode when GPU mode is on. One message
# per processed multi-camera frame, holding per-camera skeleton observations
# from a single batched ONNX call. Aggregator merges this with per-camera
# CameraNodeOutputMessage (which carries charuco only in this mode) by
# (frame_number).

@dataclass
class SkeletonInferenceResultMessage(TopicMessageABC):
    frame_number: FrameNumberInt = 0
    per_camera_skeleton: dict[CameraIdString, BaseObservation | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.frame_number < 0:
            raise ValueError(f"frame_number must be >= 0, got {self.frame_number}")


# ---------------------------------------------------------------------------
# Video (posthoc) node outputs
# ---------------------------------------------------------------------------

@dataclass
class VideoNodeOutputMessage(TopicMessageABC):
    camera_id: CameraIdString = ""
    frame_number: FrameNumberInt = 0
    observation: BaseObservation = None

    def __post_init__(self) -> None:
        if self.frame_number < 0:
            raise ValueError(f"frame_number must be >= 0, got {self.frame_number}")


# ---------------------------------------------------------------------------
# Aggregation output (realtime)
# ---------------------------------------------------------------------------

@dataclass
class AggregationNodeOutputMessage(TopicMessageABC):
    frame_number: FrameNumberInt = 0
    pipeline_id: PipelineIdString = ""
    pipeline_config: RealtimePipelineConfig = None
    camera_group_id: CameraGroupIdString = ""
    camera_node_outputs: dict[CameraIdString, CameraNodeOutputMessage] = field(default_factory=dict)
    keypoints_raw: dict[TrackedPointNameString, Point3d] = field(default_factory=dict)
    keypoints_filtered: dict[TrackedPointNameString, Point3d] = field(default_factory=dict)
    # Pre-Point3d numpy form of the same data, kept around so the websocket
    # binary serializer can ship raw bytes without re-unwrapping each
    # Pydantic model. Each value is a (3,) float array. Sparse — only points
    # that triangulated successfully are present.
    keypoints_raw_arrays: dict[TrackedPointNameString, np.ndarray] = field(default_factory=dict)
    keypoints_filtered_arrays: dict[TrackedPointNameString, np.ndarray] = field(default_factory=dict)
    rigid_body_poses: dict[str, RigidBodyPose] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.frame_number < 0:
            raise ValueError(f"frame_number must be >= 0, got {self.frame_number}")
        for cam_output in self.camera_node_outputs.values():
            if cam_output.frame_number != self.frame_number:
                raise ValueError(
                    f"CameraNodeOutputMessage for camera {cam_output.camera_id} "
                    f"has frame number {cam_output.frame_number} which does not match "
                    f"AggregationNodeOutputMessage frame number {self.frame_number}"
                )

    @property
    def charuco_overlay_data(self) -> dict:
        from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation
        from freemocap.core.viz.image_overlay.charuco_overlay_data import CharucoOverlayData

        overlay_data: dict[CameraIdString, CharucoOverlayData] = {}
        for camera_id, cam_output in self.camera_node_outputs.items():
            if cam_output.charuco_observation is not None and isinstance(cam_output.charuco_observation, CharucoObservation):
                overlay_data[camera_id] = CharucoOverlayData.from_charuco_observation(
                    camera_id=camera_id,
                    observation=cam_output.charuco_observation,
                )
        return overlay_data

    @property
    def skeleton_overlay_data(self) -> dict:
        # from skellytracker.trackers.legacy_mediapipe_tracker import LegacyMediapipeObservation
        from freemocap.core.viz.image_overlay.skeleton_overlay_data import SkeletonOverlayData
        from skellytracker.trackers.rtmpose_tracker.rtmpose_observation import RTMPoseObservation
        from skellytracker.trackers.mediapipe_tracker.composite.mediapipe_composite_observation import (
            MediapipeCompositeObservation,
        )

        overlay_data: dict[CameraIdString, SkeletonOverlayData] = {}
        for camera_id, cam_output in self.camera_node_outputs.items():
            if cam_output.skeleton_observation is None:
                continue
            if isinstance(cam_output.skeleton_observation, RTMPoseObservation):
                overlay_data[camera_id] = SkeletonOverlayData.from_rtmpose_observation(
                    camera_id=camera_id,
                    observation=cam_output.skeleton_observation,
                )
            elif isinstance(cam_output.skeleton_observation, MediapipeCompositeObservation):
                overlay_data[camera_id] = SkeletonOverlayData.from_mediapipe_composite_observation(
                    camera_id=camera_id,
                    observation=cam_output.skeleton_observation,
                )
        return overlay_data


    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.camera_node_outputs.keys())


# ---------------------------------------------------------------------------
# Pipeline stage timing (opt-in profiling)
# ---------------------------------------------------------------------------
# Each instrumented node batches its per-stage elapsed-ms samples and publishes
# them periodically. The aggregator runs a reporter thread that subscribes,
# maintains rolling buffers across all nodes, and prints one consolidated
# report. Camera-node samples for the same stage collapse across camera_id
# into ensemble statistics so adding cameras doesn't multiply log volume.
#
# Task events carry monotonic start/end timestamps, frame/camera context, and
# parent links for the metrics timeline UI.

@dataclass
class PipelineTimingEvent:
    task_id: str = ""
    parent_task_ids: list[str] = field(default_factory=list)
    stage: str = ""
    node_kind: str = ""
    camera_id: CameraIdString | None = None
    frame_number: FrameNumberInt | None = None
    start_time_ns: int = 0
    end_time_ns: int = 0
    duration_ms: float = 0.0
    batch_index: int | None = None
    batch_size: int | None = None


@dataclass
class PipelineTimingMessage(TopicMessageABC):
    node_kind: str = ""              # "camera" | "skeleton_inference" | "aggregator"
    node_label: str = ""             # human-readable label for log section headers
    camera_id: CameraIdString | None = None  # set only for camera nodes
    samples: dict[str, list[float]] = field(default_factory=dict)  # stage -> elapsed_ms batch
    events: list[PipelineTimingEvent] = field(default_factory=list)
    clock_domain: str = "perf_counter"
    relay_perf_counter_ns: int = 0
    dropped_timing_events: int = 0


# ---------------------------------------------------------------------------
# Topic instantiation
# ---------------------------------------------------------------------------

ProcessFrameNumberTopic = create_topic(ProcessFrameNumberMessage)
PipelineConfigUpdateTopic = create_topic(PipelineConfigUpdateMessage)
CameraNodeOutputTopic = create_topic(CameraNodeOutputMessage)
SkeletonInferenceResultTopic = create_topic(SkeletonInferenceResultMessage)
VideoNodeOutputTopic = create_topic(VideoNodeOutputMessage, queue_maxsize=0)  # unbounded: posthoc video nodes finish before aggregation node starts
AggregationNodeOutputTopic = create_topic(AggregationNodeOutputMessage)
PipelineTimingTopic = create_topic(PipelineTimingMessage)
