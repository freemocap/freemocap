import numpy as np
from pydantic import Field
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseObservation, TrackedPointIdString

from freemocap.core.pipeline.pipeline_configs import PipelineConfig
from freemocap.core.pubsub.pubsub_abcs import TopicMessageABC, create_topic
from freemocap.core.types.type_overloads import TrackerTypeString, FrameNumberInt, TrackedPoint3d


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

class LogRecordMessage(TopicMessageABC):
    name: str

    args: list
    levelname: str
    levelno: int
    pathname: str
    filename: str
    module: str
    lineno: int
    funcName: str
    created: float
    msecs: float
    relativeCreated: float
    thread: int
    threadName: str
    processName: str
    process: int
    delta_t: str
    message: str
    asctime: str
    formatted_message: str
    type: str
    message_type: str = "log_record"
    msg: str|None = None
    exc_info: str|tuple|None = None
    exc_text: str|None = None
    stack_info: str|None = None

ProcessFrameNumberTopic = create_topic(ProcessFrameNumberMessage)
PipelineConfigTopic = create_topic(PipelineConfigMessage)
CameraNodeOutputTopic = create_topic(CameraNodeOutputMessage)
AggregationNodeOutputTopic = create_topic(AggregationNodeOutputMessage)
