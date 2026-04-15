"""
PubSubTopicManager: auto-discovers registered topics, owns the relay thread.

Main-process only. Never pickled to children. Owned directly by the pipeline.

Lifecycle:
  - create() instantiates all topics and starts the relay thread
  - close() drains remaining messages, stops the relay, and closes all queues
"""
import logging
import multiprocessing
from dataclasses import dataclass, field
from multiprocessing import parent_process
from multiprocessing.sharedctypes import Synchronized

from freemocap.core.types.type_overloads import TopicPublicationQueue, TopicSubscriptionQueue
from freemocap.pubsub.pubsub_abcs import PubSubTopicABC, MessageType
from freemocap.pubsub.pubsub_relay import PubSubRelay

logger = logging.getLogger(__name__)


@dataclass
class PubSubTopicManager:
    """
    Manager for pub/sub topics. Auto-instantiates all registered topic classes
    and runs a relay thread for message fan-out.

    Usage:
        pubsub = PubSubTopicManager.create(global_kill_flag=flag)
        sub = pubsub.get_subscription(SomeTopic)
        pub_queue = pubsub.get_publication_queue(SomeTopic)
        pubsub.publish(SomeTopic, message)  # main-process publishing
    """

    topics: dict[type[PubSubTopicABC], PubSubTopicABC] = field(default_factory=dict)
    _relay: PubSubRelay | None = None

    @classmethod
    def create(cls, global_kill_flag: Synchronized) -> "PubSubTopicManager":
        """
        Factory: creates manager, instantiates all registered topics,
        and starts the relay thread.
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
        """Get a subscription queue for a topic. Thread-safe."""
        if parent_process() is not None:
            raise RuntimeError(
                "Subscriptions must be created in the main process "
                "and passed to children"
            )
        if self._relay is None:
            raise RuntimeError("PubSubTopicManager has no relay — was it created via create()?")

        self._relay.check_alive()
        return self._relay.create_subscription(topic_type=topic_type)

    def get_publication_queue(self, topic_type: type[PubSubTopicABC]) -> TopicPublicationQueue:
        """
        Get the publication queue for a topic.
        Returns a bare multiprocessing.Queue — pickle-safe, pass directly
        to child processes as a kwarg.
        """
        if self._relay is None:
            raise RuntimeError("PubSubTopicManager has no relay — was it created via create()?")

        self._relay.check_alive()
        return self._relay.get_publication_queue(topic_type=topic_type)

    def publish(
            self,
            topic_type: type[PubSubTopicABC[MessageType]],
            message: MessageType
    ) -> None:
        """
        Publish a message from the main process.
        For child-process publishing, use get_publication_queue() instead.
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