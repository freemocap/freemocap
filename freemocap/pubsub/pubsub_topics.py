"""
PubSub topic definitions for the pipeline system.

Each Message + Topic pair defines a typed channel. Topics auto-register
via __init_subclass__ so the PubSubTopicManager discovers them at startup.
"""
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString, MultiframeTimestampFloat
from skellytracker.core.data_primitives.observation import Observation

from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.types.type_overloads import (
    FrameNumberInt,
    PipelineIdString,
    TrackedPointNameString,
)
from freemocap.pubsub.pubsub_abcs import TopicMessageABC, create_topic

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
    charuco_observation: Observation | None = None
    skeleton_observation: Observation | None = None

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
    per_camera_skeleton: dict[CameraIdString, Observation | None] = field(default_factory=dict)

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
    observation: Observation = None

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
    keypoints_arrays: dict[TrackedPointNameString, np.ndarray] = field(default_factory=dict)
    total_body_com: np.ndarray | None = None
    xcom: np.ndarray | None = None
    standard_skeleton: dict[TrackedPointNameString, np.ndarray] | None = None
    # Per-joint named angles (radians) from the linkage layer, keyed by joint
    # name: {joint_name: (angle_0, angle_1, angle_2)} in the joint's authored
    # euler convention. None when the skeleton fitter produced no pose this
    # frame. Provenance (measured vs convention-carried inputs) lives in
    # skellyforge's JointPose objects and is not serialized yet.
    joint_angles: dict[str, tuple[float, float, float]] | None = None
    segment_rotations_world: dict[TrackedPointNameString, np.ndarray] | None = None
    segment_rotations_local: dict[TrackedPointNameString, np.ndarray] | None = None
    # Per-segment measured rest lengths (mm), keyed by segment name — the
    # rigidifier's current estimates (body + both hands). Feeds the model's
    # ``segment_lengths`` default-then-update lifecycle.
    segment_lengths: dict[str, float] = field(default_factory=dict)
    # Per-camera segment-origin landmark reprojections (camera_id → segment
    # name → (x, y) in capture-resolution px) — the fitted skeleton projected
    # back into each camera. Empty when there is no valid calibration or no
    # solved skeleton this frame (2D-only mode).
    reprojected_segment_origins: dict[
        CameraIdString, dict[TrackedPointNameString, tuple[float, float]]
    ] = field(default_factory=dict)

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

@dataclass
class PipelineTimingMessage(TopicMessageABC):
    node_kind: str = ""              # "camera" | "skeleton_inference" | "aggregator"
    node_label: str = ""             # human-readable label for log section headers
    camera_id: CameraIdString | None = None  # set only for camera nodes
    samples: dict[str, list[float]] = field(default_factory=dict)  # stage -> elapsed_ms batch


# ---------------------------------------------------------------------------
# Calibration recording state (bridge between HTTP endpoint and pipeline nodes)
# ---------------------------------------------------------------------------
# Published by the calibration HTTP endpoint when a calibration recording
# starts or stops. The CharucoRecorderNode subscribes to toggle buffering.

@dataclass
class CalibrationRecordingStateMessage(TopicMessageABC):
    recording_info: RecordingInfo | None = None
    is_active: bool = False

@dataclass
class SkeletonFitterResetMessage(TopicMessageABC):
    """Clear the rolling bone-length windows on every live pipeline.

    Presence of this message in the subscription queue signals the aggregator to
    reset its temporal state (the keypoint filter + velocity gate).
    """


# ---------------------------------------------------------------------------
# Topic instantiation
# ---------------------------------------------------------------------------

ProcessFrameNumberTopic = create_topic(ProcessFrameNumberMessage)
PipelineConfigUpdateTopic = create_topic(PipelineConfigUpdateMessage)
CameraNodeOutputTopic = create_topic(CameraNodeOutputMessage)
SkeletonInferenceResultTopic = create_topic(SkeletonInferenceResultMessage)
VideoNodeOutputTopic = create_topic(VideoNodeOutputMessage, queue_maxsize=0)  # unbounded: posthoc video nodes finish before aggregation node starts , #TODO - shouldnt thouh, agg node should run concurrently w/ video nodes
AggregationNodeOutputTopic = create_topic(AggregationNodeOutputMessage)
PipelineTimingTopic = create_topic(PipelineTimingMessage)
CalibrationRecordingStateTopic = create_topic(CalibrationRecordingStateMessage)
SkeletonFitterResetTopic = create_topic(SkeletonFitterResetMessage)


