import logging
import multiprocessing
from dataclasses import dataclass, field
from queue import Empty
from typing import TypeVar, Generic, ClassVar

from freemocap.core.types.type_overloads import TopicPublicationQueue, TopicSubscriptionQueue

logger = logging.getLogger(__name__)


@dataclass
class TopicMessageABC:
    """Base for all message data models."""
    pass


MessageType = TypeVar('MessageType', bound=TopicMessageABC)


@dataclass(eq=False)
class PubSubTopicABC(Generic[MessageType]):
    """
    Base pub/sub topic. Main-process only.

    Publishers write to the publication queue (via bare queue handles
    in children, or via publish() in the main process). The PubSubRelay
    thread reads from the publication queue and fans out to all
    subscription queues.
    """
    topic_registry: ClassVar[set[type['PubSubTopicABC']]] = set()

    message_type: type[TopicMessageABC] = TopicMessageABC
    publication: TopicPublicationQueue = field(default_factory=multiprocessing.Queue)
    subscriptions: list[TopicSubscriptionQueue] = field(default_factory=list)

    def __init_subclass__(cls, **kwargs) -> None:
        """Auto-register when subclassed."""
        super().__init_subclass__(**kwargs)
        PubSubTopicABC.topic_registry.add(cls)

    @classmethod
    def get_registered_topics(cls) -> set[type['PubSubTopicABC']]:
        return cls.topic_registry.copy()

    def get_subscription(self) -> TopicSubscriptionQueue:
        """Create and register a new subscription queue."""
        sub = multiprocessing.Queue()
        self.subscriptions.append(sub)
        return sub

    def publish(self, message: MessageType) -> None:
        """
        Publish a message by writing it to the publication queue.
        The PubSubRelay thread handles distribution to subscribers.
        """
        if not isinstance(message, self.message_type):
            raise TypeError(
                f"Message must be of type {self.message_type.__name__}, "
                f"got {type(message).__name__}"
            )
        self.publication.put(message)

    def relay_to_subscribers(self) -> int:
        """
        Drain the publication queue and fan out to all subscribers.
        Called by the PubSubRelay thread while holding the subscriptions lock.
        Returns the number of messages relayed.
        """
        relayed = 0
        while True:
            try:
                message = self.publication.get_nowait()
            except Empty:
                break
            for sub in self.subscriptions:
                sub.put(message)
            relayed += 1
        return relayed

    def close(self) -> None:
        if hasattr(self.publication, 'close'):
            self.publication.close()
        for sub in self.subscriptions:
            if hasattr(sub, 'close'):
                sub.close()
        self.subscriptions.clear()


# ============================================================================
# Factory Function
# ============================================================================

def create_topic(
        message_type: type[MessageType],
) -> type[PubSubTopicABC[MessageType]]:
    """
    Factory that creates a topic class for a message type.

    Uses type() to dynamically create a subclass — triggers auto-registration
    via __init_subclass__.
    """
    topic_name = message_type.__name__.replace('Message', 'Topic')

    topic_class = type(topic_name, (PubSubTopicABC,), {
        'message_type': message_type,
        '__module__': message_type.__module__,
    })

    return topic_class
