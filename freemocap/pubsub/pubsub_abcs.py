import logging
import multiprocessing
from dataclasses import dataclass, field
from queue import Empty, Full
from typing import TypeVar, Generic, ClassVar

from freemocap.core.types.type_overloads import TopicPublicationQueue, TopicSubscriptionQueue

logger = logging.getLogger(__name__)

_TOPIC_QUEUE_MAXSIZE: int = 100  # prevents unbounded growth when consumers lag


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

    Set queue_maxsize=0 on a subclass for an unbounded queue (e.g. topics
    where the producer can outrun the consumer before the consumer starts).
    """
    topic_registry: ClassVar[set[type['PubSubTopicABC']]] = set()
    queue_maxsize: ClassVar[int] = _TOPIC_QUEUE_MAXSIZE

    message_type: type[TopicMessageABC] = TopicMessageABC
    publication: TopicPublicationQueue = field(init=False)
    subscriptions: list[TopicSubscriptionQueue] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.publication = multiprocessing.Queue(maxsize=self.__class__.queue_maxsize)

    def __init_subclass__(cls, **kwargs) -> None:
        """Auto-register when subclassed."""
        super().__init_subclass__(**kwargs)
        PubSubTopicABC.topic_registry.add(cls)

    @classmethod
    def get_registered_topics(cls) -> set[type['PubSubTopicABC']]:
        return cls.topic_registry.copy()

    def get_subscription(self) -> TopicSubscriptionQueue:
        """Create and register a new subscription queue."""
        sub = multiprocessing.Queue(maxsize=self.__class__.queue_maxsize)
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
                try:
                    sub.put_nowait(message)
                except Full:
                    try:
                        sub.get_nowait()  # evict oldest to make room
                    except Empty:
                        pass
                    try:
                        sub.put_nowait(message)
                    except Full:
                        pass  # concurrent consumer drained it between our get and put
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
        queue_maxsize: int | None = None,
) -> type[PubSubTopicABC[MessageType]]:
    """
    Factory that creates a topic class for a message type.

    Uses type() to dynamically create a subclass — triggers auto-registration
    via __init_subclass__.

    Pass queue_maxsize=0 for an unbounded queue on topics where a slow-starting
    consumer (e.g. a child process) must not lose messages produced before it starts.
    """
    topic_name = message_type.__name__.replace('Message', 'Topic')

    attrs: dict = {
        'message_type': message_type,
        '__module__': message_type.__module__,
    }
    if queue_maxsize is not None:
        attrs['queue_maxsize'] = queue_maxsize

    topic_class = type(topic_name, (PubSubTopicABC,), attrs)

    return topic_class
