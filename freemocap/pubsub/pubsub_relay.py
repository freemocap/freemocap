"""
PubSubRelay: a dedicated thread that reads from topic publication queues
and fans out messages to all subscribers.

This decouples publishers from subscribers:
  - Publishers (in any process) only write to the publication queue
  - The relay (in the main process) handles distribution
  - Subscriptions can be added at any time without ordering constraints

The relay owns the subscriptions lock, coordinating between the main thread
(adding subscriptions) and the relay thread (iterating subscriptions).

If the relay thread dies from an unhandled exception, it sets the global_kill_flag
to bring down all processes.
"""
import logging
import multiprocessing
import threading
import time
from dataclasses import dataclass, field

from freemocap.core.types.type_overloads import TopicPublicationQueue, TopicSubscriptionQueue
from freemocap.pubsub.pubsub_abcs import PubSubTopicABC

logger = logging.getLogger(__name__)

RELAY_POLL_INTERVAL_SECONDS: float = 0.001  # 1ms idle sleep when no messages
RELAY_SHUTDOWN_TIMEOUT_SECONDS: float = 5.0
RELAY_DRAIN_TIMEOUT_SECONDS: float = 2.0


@dataclass
class PubSubRelay:
    """
    Fan-out relay thread for the pubsub system.

    Polls all topic publication queues in a tight loop. When a message
    is found, it is distributed to every subscription queue for that topic.
    On shutdown, remaining messages are drained before the thread exits.

    Owns the subscriptions lock — both create_subscription() and the relay
    loop acquire it, so subscriptions can be safely added while the relay
    is running.

    If the relay thread crashes, global_kill_flag is set immediately to
    bring down all processes.
    """
    topics: dict[type[PubSubTopicABC], PubSubTopicABC]
    global_kill_flag: multiprocessing.Value
    _subscriptions_lock: threading.Lock = field(default_factory=threading.Lock)
    _stop_event: threading.Event = field(default_factory=threading.Event)
    _thread: threading.Thread | None = field(default=None, init=False)
    _fatal_error: BaseException | None = field(default=None, init=False)

    def create_subscription(self, topic_type: type[PubSubTopicABC]) -> TopicSubscriptionQueue:
        """
        Create a new subscription queue for a topic. Thread-safe.
        Called from the main thread; coordinates with the relay thread
        via the subscriptions lock.
        """
        if topic_type not in self.topics:
            raise ValueError(
                f"Unknown topic type: {topic_type.__name__}. "
                f"Available topics: {[t.__name__ for t in self.topics.keys()]}"
            )
        with self._subscriptions_lock:
            return self.topics[topic_type].get_subscription()

    def get_publication_queue(self, topic_type: type[PubSubTopicABC]) -> TopicPublicationQueue:
        """
        Get the publication queue for a topic.
        Returns a bare multiprocessing.Queue — pickle-safe, pass directly
        to child processes as a kwarg.
        """
        if topic_type not in self.topics:
            raise ValueError(
                f"Unknown topic type: {topic_type.__name__}. "
                f"Available topics: {[t.__name__ for t in self.topics.keys()]}"
            )
        return self.topics[topic_type].publication

    def start(self) -> None:
        """Start the relay thread. Raises if already running."""
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("PubSubRelay is already running")

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._relay_loop,
            name="PubSubRelay",
            daemon=False,
        )
        self._thread.start()
        logger.debug("PubSubRelay thread started")

    def _relay_loop(self) -> None:
        """Main relay loop. Polls all publication queues and fans out messages."""
        logger.debug("PubSubRelay loop entering")
        try:
            while not self._stop_event.is_set():
                relayed_any = self._relay_one_pass()
                if not relayed_any:
                    time.sleep(RELAY_POLL_INTERVAL_SECONDS)
        except Exception as e:
            self._fatal_error = e
            logger.exception("Fatal error in PubSubRelay thread — setting global kill flag")
            self.global_kill_flag.value = True
            raise
        finally:
            logger.debug("PubSubRelay loop exiting")

    def _relay_one_pass(self) -> bool:
        """
        Do one pass over all topics, relaying any pending messages.
        Holds the subscriptions lock while iterating to coordinate
        with create_subscription().
        Returns True if any messages were relayed.
        """
        relayed_any = False
        with self._subscriptions_lock:
            for topic in self.topics.values():
                count = topic.relay_to_subscribers()
                if count > 0:
                    relayed_any = True
        return relayed_any

    def _drain(self) -> None:
        """
        Drain all remaining messages from publication queues to subscribers.
        Called during shutdown to ensure no messages are lost.
        """
        deadline = time.monotonic() + RELAY_DRAIN_TIMEOUT_SECONDS
        total_drained = 0

        while time.monotonic() < deadline:
            drained_this_pass = 0
            with self._subscriptions_lock:
                for topic in self.topics.values():
                    drained_this_pass += topic.relay_to_subscribers()
            total_drained += drained_this_pass
            if drained_this_pass == 0:
                break
            time.sleep(RELAY_POLL_INTERVAL_SECONDS)

        if total_drained > 0:
            logger.debug(f"PubSubRelay drained {total_drained} messages during shutdown")

    def check_alive(self) -> None:
        """
        Raise if the relay thread has died unexpectedly.
        Call this before operations that depend on the relay.
        """
        if self._fatal_error is not None:
            raise RuntimeError(
                "PubSubRelay thread died with a fatal error"
            ) from self._fatal_error
        if self._thread is not None and not self._thread.is_alive() and not self._stop_event.is_set():
            raise RuntimeError(
                "PubSubRelay thread died unexpectedly without a captured error"
            )

    def stop(self) -> None:
        """
        Stop the relay thread. Drains remaining messages before exiting.
        Raises RuntimeError if the thread does not stop within the timeout,
        or re-raises any fatal error that killed the relay.
        """
        if self._thread is None or not self._thread.is_alive():
            if self._fatal_error is not None:
                raise RuntimeError(
                    "PubSubRelay thread had already died with a fatal error"
                ) from self._fatal_error
            logger.debug("PubSubRelay stop called but thread is not running")
            return

        logger.debug("PubSubRelay stopping — signaling thread to exit")
        self._stop_event.set()
        self._thread.join(timeout=RELAY_SHUTDOWN_TIMEOUT_SECONDS)

        if self._thread.is_alive():
            raise RuntimeError(
                f"PubSubRelay thread did not stop within "
                f"{RELAY_SHUTDOWN_TIMEOUT_SECONDS}s timeout"
            )

        self._drain()
        logger.debug("PubSubRelay stopped")

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()