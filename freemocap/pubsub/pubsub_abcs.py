import logging
import threading
from typing import TypeVar, Generic, ClassVar
from queue import Empty

from pydantic import BaseModel, Field, ConfigDict, create_model

from freemocap.core.types.type_overloads import TopicPublicationQueue, TopicSubscriptionQueue

logger = logging.getLogger(__name__)


class TopicMessageABC(BaseModel):
    """Base for all message data models."""
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        frozen=True
    )


# MessageType represents "any type that is a subclass of TopicMessageABC"
# This allows each topic to be strongly typed with its specific message type
# e.g., PubSubTopicABC[TestMessage] means "a topic that handles TestMessage"
MessageType = TypeVar('MessageType', bound=TopicMessageABC)


class PubSubTopicABC(BaseModel, Generic[MessageType]):
    """
    Base pub/sub topic. Publishers write to the publication queue.
    The PubSubRelay thread reads from the publication queue and fans out
    to all subscription queues.
    """
    topic_registry: ClassVar[set[type['PubSubTopicABC']]] = set()

    message_type: type[TopicMessageABC]
    publication: TopicPublicationQueue = Field(default_factory=TopicPublicationQueue)
    subscriptions: list[TopicSubscriptionQueue] = Field(default_factory=list)
    _subscriptions_lock: threading.Lock = threading.Lock()

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init_subclass__(cls, **kwargs) -> None:
        """Auto-register when subclassed."""
        super().__init_subclass__(**kwargs)
        if not cls.__name__.startswith('_'):  # Skip private/base classes
            PubSubTopicABC.topic_registry.add(cls)

    @classmethod
    def get_registered_topics(cls) -> set[type['PubSubTopicABC']]:
        return cls.topic_registry.copy()

    def get_subscription(self) -> TopicSubscriptionQueue:
        """Create a new subscription queue. Thread-safe (coordinates with relay)."""
        sub = TopicSubscriptionQueue()
        with self._subscriptions_lock:
            self.subscriptions.append(sub)
        return sub

    def publish(self, message: MessageType) -> None:
        """
        Publish a message by writing it to the publication queue.
        The PubSubRelay thread handles distribution to subscribers.
        Safe to call from any process (multiprocessing.Queue is process-safe).
        """
        if not isinstance(message, self.message_type):
            raise TypeError(
                f"Message must be of type {self.message_type.__name__}, "
                f"got {type(message).__name__}"
            )
        self.publication.put(message)

    def _relay_to_subscribers(self) -> int:
        """
        Drain the publication queue and fan out to all subscribers.
        Called by the PubSubRelay thread — not for external use.
        Returns the number of messages relayed.
        """
        relayed = 0
        while True:
            try:
                message = self.publication.get_nowait()
            except Empty:
                break
            with self._subscriptions_lock:
                for sub in self.subscriptions:
                    sub.put(message)
            relayed += 1
        return relayed

    def close(self) -> None:
        if hasattr(self.publication, 'close'):
            self.publication.close()
        with self._subscriptions_lock:
            for sub in self.subscriptions:
                if hasattr(sub, 'close'):
                    sub.close()
            self.subscriptions.clear()

    def __getstate__(self) -> dict:
        """Exclude the threading.Lock when pickling (for child processes)."""
        state = self.__dict__.copy()
        state.pop('_subscriptions_lock', None)
        return state

    def __setstate__(self, state: dict) -> None:
        """Recreate the lock after unpickling."""
        self.__dict__.update(state)
        self._subscriptions_lock = threading.Lock()


# ============================================================================
# Factory Function - Eliminates Boilerplate Using Pydantic's create_model
# ============================================================================

def create_topic(
        message_type: type[MessageType],
) -> type[PubSubTopicABC[MessageType]]:
    """
    Factory that creates a topic class for a message type.

    Uses Pydantic's create_model() to properly create the class.
    Returns a class (not instance) so it auto-registers via __init_subclass__.
    """
    topic_name = message_type.__name__.replace('Message', 'Topic')

    field_definitions: dict[str, object] = {
        'message_type': (type[MessageType], message_type),
    }

    topic_class = create_model(
        topic_name,
        __base__=PubSubTopicABC,
        __module__=message_type.__module__,
        **field_definitions
    )

    return topic_class