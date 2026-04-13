"""
PubSub topic definitions for the pipeline system.

Each Message + Topic pair defines a typed channel. Topics auto-register
via __init_subclass__ so the PubSubTopicManager discovers them at startup.
"""
import logging
from typing import TYPE_CHECKING, Self

from pydantic import Field, model_validator, ConfigDict
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString, MultiframeTimestampFloat
from skellyforge.data_models.trajectory_3d import Point3d
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseObservation

from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.tasks.mocap.skeleton_dewiggler.dewiggling_methods.rigid_body_estimator import RigidBodyPose
from freemocap.core.types.type_overloads import (
    FrameNumberInt,
    PipelineIdString,
    VideoIdString,
    TrackedPointNameString,
)
from freemocap.pubsub.pubsub_abcs import TopicMessageABC, create_topic

if TYPE_CHECKING:
    from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation
    from skellytracker.trackers.mediapipe_tracker import MediapipeObservation
    from freemocap.core.viz.image_overlay.charuco_overlay_data import CharucoOverlayData
    from freemocap.core.viz.image_overlay.mediapipe_overlay_data import MediapipeOverlayData

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Frame processing
# ---------------------------------------------------------------------------

class ProcessFrameNumberMessage(TopicMessageABC):
    frame_number: int = Field(ge=0, description="Frame number to process")


# ---------------------------------------------------------------------------
# Config updates
# ---------------------------------------------------------------------------

class PipelineConfigUpdateMessage(TopicMessageABC):
    pipeline_config: RealtimePipelineConfig


# ---------------------------------------------------------------------------
# Realtime node outputs
# ---------------------------------------------------------------------------

class CameraNodeOutputMessage(TopicMessageABC):
    camera_id: CameraIdString
    frame_number: FrameNumberInt = Field(ge=0)
    charuco_observation: BaseObservation | None
    mediapipe_observation: BaseObservation | None


# ---------------------------------------------------------------------------
# Video (posthoc) node outputs
# ---------------------------------------------------------------------------

class VideoNodeOutputMessage(TopicMessageABC):
    video_id: VideoIdString
    frame_number: FrameNumberInt = Field(ge=0)
    observation: BaseObservation


# ---------------------------------------------------------------------------
# Aggregation output (realtime)
# ---------------------------------------------------------------------------

class AggregationNodeOutputMessage(TopicMessageABC):
    frame_number: FrameNumberInt = Field(ge=0)
    pipeline_id: PipelineIdString
    pipeline_config: RealtimePipelineConfig
    camera_group_id: CameraGroupIdString
    camera_node_outputs: dict[CameraIdString, CameraNodeOutputMessage]
    keypoints_raw: dict[TrackedPointNameString, Point3d] = Field(default_factory=dict)
    keypoints_filtered: dict[TrackedPointNameString, Point3d] = Field(default_factory=dict)
    rigid_body_poses: dict[str, RigidBodyPose] = Field(default_factory=dict)

    @model_validator(mode='after')
    def validate(self) -> 'AggregationNodeOutputMessage':
        for cam_output in self.camera_node_outputs.values():
            if cam_output.frame_number != self.frame_number:
                raise ValueError(
                    f"CameraNodeOutputMessage for camera {cam_output.camera_id} "
                    f"has frame number {cam_output.frame_number} which does not match "
                    f"AggregationNodeOutputMessage frame number {self.frame_number}"
                )
        return self

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
    def mediapipe_overlay_data(self) -> dict:
        from skellytracker.trackers.legacy_mediapipe_tracker import LegacyMediapipeObservation
        from freemocap.core.viz.image_overlay.mediapipe_overlay_data import MediapipeOverlayData

        overlay_data: dict[CameraIdString, MediapipeOverlayData] = {}
        for camera_id, cam_output in self.camera_node_outputs.items():
            if cam_output.mediapipe_observation is not None and isinstance(cam_output.mediapipe_observation, LegacyMediapipeObservation):
                overlay_data[camera_id] = MediapipeOverlayData.from_mediapipe_observation(
                    camera_id=camera_id,
                    observation=cam_output.mediapipe_observation,
                )
        return overlay_data

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.camera_node_outputs.keys())


# ---------------------------------------------------------------------------
# Posthoc progress reporting
# ---------------------------------------------------------------------------

class PipelineProgressMessage(TopicMessageABC):
    pipeline_id: PipelineIdString
    frame_count: int = Field(ge=0)
    last_processed: FrameNumberInt = Field(ge=-1, default=-1)
    working: bool = False
    complete: bool = False
    error:bool = False
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        frozen=False
    )

    def increment(self) -> Self:
        if not self.working:
            self.working = True
        if self.last_processed + 1 >= self.frame_count:
            self.complete = True
            self.working = False
        if self.last_processed > self.frame_count:
            raise ValueError(
                f"Cannot increment last_processed beyond frame_count: "
                f"{self.last_processed} + 1 > {self.frame_count}"
            )
        self.last_processed += 1
        return self



class VideoNodeProgressMessage(PipelineProgressMessage):
    video_id: VideoIdString


class AggregatorNodeProgressMessage(PipelineProgressMessage):
    running_aggregation_task: bool = Field(default=False)


# ---------------------------------------------------------------------------
# Topic instantiation
# ---------------------------------------------------------------------------

ProcessFrameNumberTopic = create_topic(ProcessFrameNumberMessage)
PipelineConfigUpdateTopic = create_topic(PipelineConfigUpdateMessage)
CameraNodeOutputTopic = create_topic(CameraNodeOutputMessage)
VideoNodeOutputTopic = create_topic(VideoNodeOutputMessage)
AggregationNodeOutputTopic = create_topic(AggregationNodeOutputMessage)
VideoNodeProgressTopic = create_topic(VideoNodeProgressMessage)
AggregatorNodeProgressTopic = create_topic(AggregatorNodeProgressMessage)
