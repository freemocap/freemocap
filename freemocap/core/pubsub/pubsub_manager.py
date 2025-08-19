import logging
from enum import Enum, auto
from multiprocessing.process import parent_process

from pydantic import BaseModel, ConfigDict, Field

from skellycam.core.ipc.pubsub.pubsub_abcs import PubSubTopicABC
from skellycam.core.ipc.pubsub.pubsub_topics import LogsTopic, UpdateCamerasSettingsTopic, DeviceExtractedConfigTopic, \
    SetShmTopic, RecordingInfoTopic, RecordingFinishedTopic, FramerateTopic
from skellycam.core.types.type_overloads import CameraGroupIdString, TopicSubscriptionQueue

logger = logging.getLogger(__name__)


class TopicTypes(Enum):
    UPDATE_CAMERA_SETTINGS = auto() #User requested updates to camera configs (i.e. the desired camera settings)
    EXTRACTED_CONFIG = auto() #Camera Configs extracted from the camera (i.e. the actual camera settings)
    SHM_UPDATES = auto()
    RECORDING_INFO = auto()
    RECORDING_FINISHED = auto()
    FRAMERATE = auto() #Framerate updates for cameras
    LOGS = auto()


class PubSubTopicManager(BaseModel):
    topics: dict[TopicTypes, PubSubTopicABC] = Field(default_factory=lambda: {
        TopicTypes.UPDATE_CAMERA_SETTINGS: UpdateCamerasSettingsTopic(),
        TopicTypes.EXTRACTED_CONFIG: DeviceExtractedConfigTopic(),
        TopicTypes.SHM_UPDATES: SetShmTopic(),
        TopicTypes.RECORDING_INFO: RecordingInfoTopic(),
        TopicTypes.RECORDING_FINISHED: RecordingFinishedTopic(),
        TopicTypes.FRAMERATE: FramerateTopic(),
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




PUB_SUB_MANAGERS: dict[CameraGroupIdString, PubSubTopicManager] = {}


def create_pubsub_manager(group_id: CameraGroupIdString) -> PubSubTopicManager:
    """
    Create a global PubSubManager instance, raises an error if called in a non-main process.
    """
    global PUB_SUB_MANAGERS
    if parent_process() is not None:
        raise RuntimeError("PubSubManager can only be created in the main process.")
    if PUB_SUB_MANAGERS.get(group_id) is not None:
        logger.debug(f"Creating PubSubManager for group {group_id}")
        PUB_SUB_MANAGERS.get(group_id).close()
    PUB_SUB_MANAGERS[group_id] = PubSubTopicManager()
    return PUB_SUB_MANAGERS[group_id]


