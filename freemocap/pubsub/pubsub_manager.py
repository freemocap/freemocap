"""
PubSubTopicManager: auto-discovers registered topics, owns the relay thread.

The relay thread handles all message fan-out from publication queues to
subscriber queues. This eliminates ordering dependencies during node creation —
subscriptions can be added at any time and will receive all future messages.

Lifecycle:
  - create() instantiates all topics and starts the relay thread
  - close() drains remaining messages, stops the relay, and closes all queues

If the relay thread dies unexpectedly, it sets the global_kill_flag to
bring down all processes.
"""
import logging
import multiprocessing
from multiprocessing import parent_process

from pydantic import BaseModel, Field, ConfigDict

from freemocap.core.types.type_overloads import TopicSubscriptionQueue, PipelineIdString
from freemocap.pubsub.pubsub_abcs import PubSubTopicABC, MessageType
from freemocap.pubsub.pubsub_relay import PubSubRelay

logger = logging.getLogger(__name__)


class PubSubTopicManager(BaseModel):
    """
    Manager for pub/sub topics. Auto-instantiates all registered topic classes
    and runs a relay thread for message fan-out.

    Usage:
        manager = PubSubTopicManager.create(global_kill_flag=flag)
        sub = manager.get_subscription(ProcessFrameNumberTopic)
        manager.publish(ProcessFrameNumberTopic, message)
    """

    topics: dict[type[PubSubTopicABC], PubSubTopicABC] = Field(default_factory=dict)
    _relay: PubSubRelay | None = Field(default=None, exclude=True)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def create(cls, global_kill_flag: multiprocessing.Value) -> "PubSubTopicManager":
        """
        Factory: creates manager, instantiates all registered topics,
        and starts the relay thread.

        Args:
            global_kill_flag: Set by the relay if it crashes, bringing down all processes.
        """
        if parent_process() is not None:
            raise RuntimeError("PubSubTopicManager must be created in the main process")

        manager = cls()
        for topic_cls in PubSubTopicABC.get_registered_topics():
            manager.topics[topic_cls] = topic_cls()
            logger.debug(f"Instantiated topic: {topic_cls.__name__}")

        manager._relay = PubSubRelay(
            topics=manager.topics,
            global_kill_flag=global_kill_flag,
        )
        manager._relay.start()
        logger.debug(
            f"PubSubTopicManager created with {len(manager.topics)} topics "
            f"and relay thread started"
        )
        return manager

    def get_subscription(self, topic_type: type[PubSubTopicABC]) -> TopicSubscriptionQueue:
        """
        Get a subscription queue for a topic. Thread-safe.

        Args:
            topic_type: The topic CLASS (e.g., ProcessFrameNumberTopic)
        """
        if parent_process() is not None:
            raise RuntimeError(
                "Subscriptions must be created in the main process "
                "and passed to children"
            )

        if topic_type not in self.topics:
            raise ValueError(
                f"Unknown topic type: {topic_type.__name__}. "
                f"Available topics: {[t.__name__ for t in self.topics.keys()]}"
            )

        if self._relay is not None:
            self._relay.check_alive()

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
        Publish a message to a topic's publication queue.
        The relay thread handles distribution to subscribers.

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
        """Stop the relay thread (draining remaining messages), then close all topics."""
        logger.debug("Closing PubSubTopicManager...")

        if self._relay is not None:
            self._relay.stop()
            self._relay = None

        for topic in self.topics.values():
            topic.close()
        self.topics.clear()

        logger.debug("PubSubTopicManager closed.")


# ============================================================================
# Global pipeline manager registry
# ============================================================================

PIPELINE_PUB_SUB_MANAGERS: dict[PipelineIdString, PubSubTopicManager] = {}


def create_pipeline_pubsub_manager(
    pipeline_id: PipelineIdString,
    global_kill_flag: multiprocessing.Value,
) -> PubSubTopicManager:
    """Create/replace manager for a pipeline. Must be called from main process."""
    global PIPELINE_PUB_SUB_MANAGERS

    if parent_process() is not None:
        raise RuntimeError("PubSubManager can only be created in the main process.")

    if PIPELINE_PUB_SUB_MANAGERS.get(pipeline_id) is not None:
        logger.debug(f"Closing existing PubSubManager for pipeline {pipeline_id}")
        PIPELINE_PUB_SUB_MANAGERS[pipeline_id].close()

    logger.debug(f"Creating PubSubManager for pipeline {pipeline_id}")
    PIPELINE_PUB_SUB_MANAGERS[pipeline_id] = PubSubTopicManager.create(
        global_kill_flag=global_kill_flag,
    )
    return PIPELINE_PUB_SUB_MANAGERS[pipeline_id]