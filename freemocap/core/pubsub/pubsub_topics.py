from pydantic import Field
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString
from skellytracker.trackers.base_tracker.base_tracker_abcs import TrackedPointIdString
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.core.pipeline.pipeline_configs import PipelineConfig
from freemocap.core.pubsub.pubsub_abcs import TopicMessageABC, create_topic
from freemocap.core.types.type_overloads import TrackerTypeString, FrameNumberInt, Point3d


class ProcessFrameNumberMessage(TopicMessageABC):
    frame_number: int = Field(ge=0, description="Frame number to process")


class PipelineConfigMessage(TopicMessageABC):
    pipeline_config: PipelineConfig


class CameraNodeOutputMessage(TopicMessageABC):
    camera_id: CameraIdString
    frame_number: FrameNumberInt
    tracker_name: TrackerTypeString
    charuco_observation: CharucoObservation|None = None



class AggregationNodeOutputMessage(TopicMessageABC):
    frame_number: FrameNumberInt
    camera_group_id: CameraGroupIdString
    tracked_points3d: dict[TrackedPointIdString,Point3d] = Field(default_factory=dict)

ProcessFrameNumberTopic = create_topic(ProcessFrameNumberMessage)
PipelineConfigTopic = create_topic(PipelineConfigMessage)
CameraNodeOutputTopic = create_topic(CameraNodeOutputMessage)
AggregationNodeOutputTopic = create_topic(AggregationNodeOutputMessage)
