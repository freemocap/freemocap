import logging
from enum import Enum, auto
from multiprocessing.process import parent_process

from pydantic import BaseModel, ConfigDict, Field
from skellycam.core.ipc.pubsub.pubsub_abcs import PubSubTopicABC
from skellycam.core.types.type_overloads import TopicSubscriptionQueue

from freemocap.core.pubsub.pubsub_topics import LogsTopic, ProcessFrameNumberTopic, SkellyTrackerConfigsTopic, \
    CameraNodeOutputTopic
from freemocap.core.types.type_overloads import PipelineIdString

logger = logging.getLogger(__name__)


class TopicTypes(Enum):
    PROCESS_FRAME_NUMBER = auto()  # Imperative to process a particular frame number
    SKELLY_TRACKER_CONFIGS = auto()  # Skelly Tracker configuration updates
    CAMERA_NODE_OUTPUT = auto()  # Output from camera nodes
    AGGREGATION_NODE_OUTPUT = auto()  # Output from aggregation node
    LOGS = auto()


class PubSubTopicManager(BaseModel):
    topics: dict[TopicTypes, PubSubTopicABC] = Field(default_factory=lambda: {
        TopicTypes.PROCESS_FRAME_NUMBER: ProcessFrameNumberTopic(),
        TopicTypes.SKELLY_TRACKER_CONFIGS: SkellyTrackerConfigsTopic(),
        TopicTypes.CAMERA_NODE_OUTPUT: CameraNodeOutputTopic(),
        TopicTypes.AGGREGATION_NODE_OUTPUT: AggregationNodeOutputTopic(),
        TopicTypes.LOGS: LogsTopic(),
    })
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    def get_subscription(self, topic_type: TopicTypes) -> TopicSubscriptionQueue:
        """
        Get a subscription queue for a specific topic type.
        Raises an error if the topic type is not recognized.
        """
        if parent_process() is not None:
            raise RuntimeError("Subscriptions must be created in the main process and passed to children")


        if topic_type not in self.topics:
            raise ValueError(f"Unknown topic type: {topic_type}")
        sub= self.topics[topic_type].get_subscription()
        logger.trace(f"Subscribed to topic {topic_type.name} with {len(self.topics[topic_type].subscriptions)} subscriptions")
        return sub

    def close(self) -> None:
        """
        Close all topics in the manager.
        """
        logger.debug("Closing PubSubTopicManager...")
        for topic in self.topics.values():
            topic.close()
        self.topics.clear()
        logger.debug("PubSubTopicManager closed.")




PIPELINE_PUB_SUB_MANAGERS: dict[PipelineIdString, PubSubTopicManager] = {}


def create_pipeline_pubsub_manager(pipeline_id: PipelineIdString) -> PubSubTopicManager:
    """
    Create a global PubSubManager instance, raises an error if called in a non-main process.
    """
    global PIPELINE_PUB_SUB_MANAGERS
    if parent_process() is not None:
        raise RuntimeError("PubSubManager can only be created in the main process.")
    if PIPELINE_PUB_SUB_MANAGERS.get(pipeline_id) is not None:
        logger.debug(f"Creating PubSubManager for group {pipeline_id}")
        PIPELINE_PUB_SUB_MANAGERS.get(pipeline_id).close()
    PIPELINE_PUB_SUB_MANAGERS[pipeline_id] = PubSubTopicManager()
    return PIPELINE_PUB_SUB_MANAGERS[pipeline_id]


