import numpy as np
from pydantic import Field
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseObservation, TrackedPointIdString

from freemocap.core.pipeline.processing_pipeline import PipelineConfig
from freemocap.core.pubsub.pubsub_abcs import TopicMessageABC, create_topic
from freemocap.core.types.type_overloads import TrackerTypeString, FrameNumberInt, TrackedPoint3d
from freemocap.system.logging_configuration.handlers.websocket_log_queue_handler import LogRecordModel, \
    get_websocket_log_queue


class ProcessFrameNumberMessage(TopicMessageABC):
    frame_number: int = Field(ge=0, description="Frame number to process")


class PipelineConfigMessage(TopicMessageABC):
    pipeline_config: PipelineConfig


class CameraNodeOutputMessage(TopicMessageABC):
    frame_metadata: np.recarray
    tracker_name: TrackerTypeString
    observation: BaseObservation

    @property
    def camera_id(self) -> CameraIdString:
        return self.frame_metadata.camera_config.camera_id[0]


class AggregationNodeOutputMessage(TopicMessageABC):
    frame_number: FrameNumberInt
    camera_group_id: CameraGroupIdString
    tracker_name: TrackerTypeString
    tracked_points3d: dict[TrackedPointIdString, TrackedPoint3d] = Field(default_factory=dict)


ProcessFrameNumberTopic = create_topic(ProcessFrameNumberMessage)
PipelineConfigTopic = create_topic(PipelineConfigMessage)
CameraNodeOutputTopic = create_topic(CameraNodeOutputMessage)
AggregationNodeOutputTopic = create_topic(AggregationNodeOutputMessage)
#TODO - better integrate log publishing thing with the pubsub system
LogsTopic = create_topic(LogRecordModel, publication_factory=get_websocket_log_queue)
