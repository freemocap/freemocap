"""
Base abstractions for process-based pipeline nodes.
"""
import logging
import multiprocessing
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel, Field, ConfigDict

from freemocap.core.types.type_overloads import TopicSubscriptionQueue
from freemocap.pubsub.pubsub_abcs import PubSubTopicABC
from freemocap.pubsub.pubsub_manager import PubSubTopicManager

logger = logging.getLogger(__name__)


class PipelineType(Enum):
    """Pipeline execution modes - NO HYBRID ALLOWED."""
    REALTIME = "realtime"  # Process frames from live camera feeds
    POSTHOC = "posthoc"    # Process recorded data from disk


class ProcessNodeParams(BaseModel):
    """Base configuration for all process nodes."""
    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )
    
    # Declarative topic requirements
    subscribed_topics: ClassVar[list[type[PubSubTopicABC]]] = []
    published_topics: ClassVar[list[type[PubSubTopicABC]]] = []
    
    @classmethod
    def get_subscription_requirements(cls) -> list[type[PubSubTopicABC]]:
        """Get topics this node needs to subscribe to."""
        return cls.subscribed_topics
    
    @classmethod
    def get_publication_topics(cls) -> list[type[PubSubTopicABC]]:
        """Get topics this node will publish to."""
        return cls.published_topics


class ProcessNodeABC(BaseModel,ABC):
    """
    Abstract base class for all process-based pipeline nodes.
    
    CRITICAL: Subscriptions MUST be created in parent process and passed to create().
    Nodes can publish to any topic but can only subscribe to pre-allocated subscriptions.

    node_id: Unique identifier for this node instance
    params: Node configuration parameters
    subscriptions: Pre-allocated subscription queues (created in parent!)
    pubsub: PubSub manager for publishing only
    shutdown_flag: Multiprocessing flag for shutdown signaling
    worker: The multiprocessing.Process worker
    """
    
    node_id: str
    params: ProcessNodeParams
    subscriptions: dict[type[PubSubTopicABC], TopicSubscriptionQueue]
    pubsub: PubSubTopicManager
    shutdown_flag: multiprocessing.Value
    worker: multiprocessing.Process

    @classmethod
    @abstractmethod
    def create(
        cls,
        *,
        node_id: str,
        params: ProcessNodeParams,
        subscriptions: dict[type[PubSubTopicABC], TopicSubscriptionQueue],
        pubsub: PubSubTopicManager,
        subprocess_registry: list[multiprocessing.Process],
        **kwargs: Any
    ) -> "ProcessNodeABC":
        """
        Factory method to create node with pre-allocated subscriptions.
        
        MUST be called from parent process to properly allocate subscriptions!
        
        Args:
            node_id: Unique identifier for this node
            params: Node configuration
            subscriptions: Pre-created subscription queues
            pubsub: PubSub manager (for publishing only in child process)
            subprocess_registry: Registry to add worker process to
            **kwargs: Additional node-specific resources
        
        Returns:
            Initialized node instance
        """
        raise NotImplementedError
    
    @staticmethod
    @abstractmethod
    def _run(
        *,
        node_id: str,
        params: ProcessNodeParams,
        subscriptions: dict[type[PubSubTopicABC], TopicSubscriptionQueue],
        pubsub: PubSubTopicManager,
        shutdown_flag: multiprocessing.Value,
        **kwargs: Any
    ) -> None:
        """
        Main process loop - runs in child process.
        
        Args:
            node_id: Node identifier
            params: Configuration parameters
            subscriptions: Pre-allocated subscription queues
            pubsub: PubSub manager for publishing
            shutdown_flag: Shutdown signal
            **kwargs: Additional resources
        """
        raise NotImplementedError
    
    def start(self) -> None:
        """Start the worker process."""
        logger.debug(f"Starting {self.__class__.__name__} node {self.node_id}")
        self.worker.start()
    
    def shutdown(self) -> None:
        """Shutdown the worker process gracefully."""
        logger.debug(f"Shutting down {self.__class__.__name__} node {self.node_id}")
        self.shutdown_flag.value = True
        self.worker.join(timeout=5.0)
        if self.worker.is_alive():
            logger.warning(f"Force terminating {self.__class__.__name__} node {self.node_id}")
            self.worker.terminate()
            self.worker.join(timeout=2.0)
    
    @property
    def is_alive(self) -> bool:
        """Check if worker process is alive."""
        return self.worker.is_alive()


class NodeState(BaseModel):
    """Base state representation for nodes."""
    model_config = ConfigDict(
        frozen=True,
        arbitrary_types_allowed=True
    )
    
    node_id: str
    node_type: str
    is_alive: bool
    last_activity_time: float | None = None

