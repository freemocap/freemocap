
# ============================================================================
# PubSubTopicManager - Auto-discovers and manages all registered topics
# ============================================================================

import logging
from multiprocessing import parent_process

from pydantic import BaseModel, Field, ConfigDict

from freemocap.pubsub.pubsub_abcs import PubSubTopicABC, MessageType
from freemocap.core.types.type_overloads import TopicSubscriptionQueue, PipelineIdString

logger = logging.getLogger(__name__)

class PubSubTopicManager(BaseModel):
    """
    Manager for pub/sub topics. Auto-instantiates all registered topic classes.

    Usage:
        manager = PubSubTopicManager.create()
        sub = manager.get_subscription(ProcessFrameNumberTopic)
        manager.publish(ProcessFrameNumberTopic, message)
    """

    # Dict maps topic classes to their instances: {ProcessFrameNumberTopic: <instance>}
    topics: dict[type[PubSubTopicABC], PubSubTopicABC] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def create(cls) -> "PubSubTopicManager":
        """Factory method: creates manager and auto-instantiates all registered topics."""
        manager = cls()
        for topic_cls in PubSubTopicABC.get_registered_topics():
            manager.topics[topic_cls] = topic_cls()
            logger.debug(f"Instantiated topic: {topic_cls.__name__}")
        return manager

    def get_subscription(self, topic_type: type[PubSubTopicABC]) -> TopicSubscriptionQueue:
        """
        Get a subscription queue for a topic.

        Args:
            topic_type: The topic CLASS (e.g., ProcessFrameNumberTopic)
        """
        if parent_process() is not None:
            raise RuntimeError("Subscriptions must be created in the main process and passed to children")

        if topic_type not in self.topics:
            raise ValueError(
                f"Unknown topic type: {topic_type.__name__}. "
                f"Available topics: {[t.__name__ for t in self.topics.keys()]}"
            )

        sub = self.topics[topic_type].get_subscription()
        logger.trace(
            f"Subscribed to topic {topic_type.__name__} "
            f"with {len(self.topics[topic_type].subscriptions)} subscriptions"
        )
        return sub

    def publish(
        self,
        topic_type: type[PubSubTopicABC[MessageType]],
        message: MessageType
    ) -> None:
        """
        Publish a message to a topic.

        Args:
            topic_type: The topic CLASS to publish to
            message: The message to publish
        """
        if topic_type not in self.topics:
            raise ValueError(
                f"Unknown topic type: {topic_type.__name__}. "
                f"Available topics: {[t.__name__ for t in self.topics.keys()]}"
            )

        self.topics[topic_type].publish(message)

    def close(self) -> None:
        """Close all topics in the manager."""
        logger.debug("Closing PubSubTopicManager...")
        for topic in self.topics.values():
            topic.close()
        self.topics.clear()
        logger.debug("PubSubTopicManager closed.")


# ============================================================================
# Global pipeline manager registry
# ============================================================================

PIPELINE_PUB_SUB_MANAGERS: dict[PipelineIdString, PubSubTopicManager] = {}


def create_pipeline_pubsub_manager(pipeline_id: PipelineIdString) -> PubSubTopicManager:
    """Create/replace manager for a pipeline. Must be called from main process."""
    global PIPELINE_PUB_SUB_MANAGERS

    if parent_process() is not None:
        raise RuntimeError("PubSubManager can only be created in the main process.")

    if PIPELINE_PUB_SUB_MANAGERS.get(pipeline_id) is not None:
        logger.debug(f"Closing existing PubSubManager for pipeline {pipeline_id}")
        PIPELINE_PUB_SUB_MANAGERS[pipeline_id].close()

    logger.debug(f"Creating PubSubManager for pipeline {pipeline_id}")
    PIPELINE_PUB_SUB_MANAGERS[pipeline_id] = PubSubTopicManager.create()
    return PIPELINE_PUB_SUB_MANAGERS[pipeline_id]