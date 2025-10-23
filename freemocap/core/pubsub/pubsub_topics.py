from typing import Type

import numpy as np
from pydantic import Field
from skellycam.core.ipc.pubsub.pubsub_abcs import PubSubTopicABC, TopicMessageABC
from skellycam.core.types.type_overloads import TopicPublicationQueue, CameraGroupIdString, FrameNumberInt
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseTrackerConfig, BaseObservation, \
    TrackedPointIdString
from skellytracker.trackers.base_tracker.base_tracker_abcs import TrackerTypeString

from freemocap.core.types.type_overloads import TrackedPoint3d
from freemocap.system.logging_configuration.handlers.websocket_log_queue_handler import LogRecordModel, \
    get_websocket_log_queue


class ProcessFrameNumberMessage(TopicMessageABC):
    """
    Message containing the frame number of the current process.
    This is used to synchronize frame processing across multiple processes.
    """
    frame_number: int = Field(ge=0, description="Imperative to process this frame number")


class PipelineConfigMessage(TopicMessageABC):
    """
    Message containing the Pipeline configuration updates.
    """
    pipeline_config: PipelineConfig

class CameraNodeOutputMessage(TopicMessageABC):
    """
    Message containing the output data from a camera node.
    This is used to pass processed camera data to the next stage in the pipeline.
    """
    frame_metadata: np.recarray = Field(
        description="Metadata of the frame processed by the camera node.",)
    tracker_name: TrackerTypeString = Field(
        description="Name of the tracker used to process the observation.")
    observation: BaseObservation = Field(
        description="Observation object produced by a Skellytracker Tracker object.",
    )

    @property
    def camera_id(self) -> str:
        """
        Returns the camera ID associated with the frame metadata.
        This is used to identify which camera produced the data.
        """
        return self.frame_metadata.camera_config.camera_id[0]

    @property
    def tracker_type(self)  -> TrackerTypeString:
        """
        Returns the type of tracker used to process the observation.
        This is used to identify the tracker that produced the data.
        """
        return self.observation.tracker_type


class AggregationNodeOutputMessage(TopicMessageABC):
    """
    Message containing the output data from an aggregation node.
    This is used to pass aggregated data to the next stage in the pipeline.
    """
    frame_number: FrameNumberInt
    camera_group_id: CameraGroupIdString
    tracker_name: TrackerTypeString
    tracked_points3d: dict[TrackedPointIdString, TrackedPoint3d] = Field(
        default_factory=dict,
        description="Dictionary containing 3D data for tracked points, where keys are tracked point IDs and values are 3D coordinates.")


class CameraNodeOutputTopic(PubSubTopicABC):
    """
    Topic for publishing the output data from a camera node.
    This is used to pass processed camera data to the next stage in the pipeline.
    """
    message_type: Type[CameraNodeOutputMessage] = CameraNodeOutputMessage

class AggregationNodeOutputTopic(PubSubTopicABC):
    """
    Topic for publishing the output data from an aggregation node.
    This is used to pass aggregated data to the next stage in the pipeline.
    """
    message_type: Type[AggregationNodeOutputMessage] = AggregationNodeOutputMessage
class ProcessFrameNumberTopic(PubSubTopicABC):
    """
    Topic for publishing the frame number of the current process.
    This is used to synchronize frame processing across multiple processes.
    """
    message_type: Type[ProcessFrameNumberMessage] = ProcessFrameNumberMessage


class PipelineConfigTopic(PubSubTopicABC):
    """
    Topic for publishing Pipeline config updates
    """
    message_type: Type[PipelineConfigMessage] = PipelineConfigMessage


class LogsTopic(PubSubTopicABC):
    message_type: Type[LogRecordModel] = LogRecordModel
    publication: TopicPublicationQueue = Field(default_factory=get_websocket_log_queue)
