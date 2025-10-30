from multiprocessing import Queue
from queue import Empty
from typing import Any

import pytest
from pydantic import Field

from freemocap.core.pubsub.pubsub_abcs import (
    TopicMessageABC,
    PubSubTopicABC,
    create_topic,
)
from freemocap.core.pubsub.pubsub_manager import (
    PubSubTopicManager,
    create_pipeline_pubsub_manager,
    PIPELINE_PUB_SUB_MANAGERS,
)


# ============================================================================
# Test Fixtures - Message Types
# ============================================================================

class TestMessage(TopicMessageABC):
    """Simple test message."""
    value: int


class TestMessageWithData(TopicMessageABC):
    """Test message with more fields."""
    name: str
    count: int = Field(ge=0)
    data: dict[str, Any] = Field(default_factory=dict)


class AnotherTestMessage(TopicMessageABC):
    """Another message type for testing."""
    text: str


# ============================================================================
# Test Fixtures - Topics
# ============================================================================

@pytest.fixture(autouse=True)
def clear_topic_registry() -> None:
    """Clear the topic registry before each test."""
    PubSubTopicABC.topic_registry.clear()
    PIPELINE_PUB_SUB_MANAGERS.clear()
    yield
    PubSubTopicABC.topic_registry.clear()
    PIPELINE_PUB_SUB_MANAGERS.clear()


@pytest.fixture
def test_topic_class() -> type[PubSubTopicABC[TestMessage]]:
    """Create a test topic class."""
    return create_topic(message_type=TestMessage)


@pytest.fixture
def test_topic_instance(test_topic_class: type[PubSubTopicABC[TestMessage]]) -> PubSubTopicABC[TestMessage]:
    """Create an instance of test topic."""
    return test_topic_class()


# ============================================================================
# Tests for TopicMessageABC
# ============================================================================

def test_topic_message_creation() -> None:
    """Test basic message creation."""
    msg = TestMessage(value=42)
    assert msg.value == 42


def test_topic_message_validation() -> None:
    """Test message validation."""
    # Should work
    msg = TestMessageWithData(name="test", count=5)
    assert msg.name == "test"
    assert msg.count == 5
    
    # Should fail validation (count must be >= 0)
    with pytest.raises(Exception):  # Pydantic validation error
        TestMessageWithData(name="test", count=-1)


# ============================================================================
# Tests for PubSubTopicABC - Registration
# ============================================================================

def test_topic_auto_registration() -> None:
    """Test that topics auto-register on subclassing."""
    initial_count = len(PubSubTopicABC.topic_registry)
    
    # Create a new topic
    TestTopic = create_topic(message_type=TestMessage)
    
    # Should be registered
    assert len(PubSubTopicABC.topic_registry) == initial_count + 1
    assert TestTopic in PubSubTopicABC.topic_registry


def test_topic_private_classes_not_registered() -> None:
    """Test that private topic classes (starting with _) are not registered."""
    initial_count = len(PubSubTopicABC.topic_registry)
    
    class _PrivateTestTopic(PubSubTopicABC[TestMessage]):
        message_type: type[TestMessage] = TestMessage
    
    # Should NOT be registered
    assert len(PubSubTopicABC.topic_registry) == initial_count
    assert _PrivateTestTopic not in PubSubTopicABC.topic_registry


def test_get_registered_topics() -> None:
    """Test getting registered topics returns a copy."""
    TestTopic1 = create_topic(message_type=TestMessage)
    TestTopic2 = create_topic(message_type=AnotherTestMessage)
    
    topics = PubSubTopicABC.get_registered_topics()
    
    assert TestTopic1 in topics
    assert TestTopic2 in topics
    
    # Should be a copy, not the original
    topics.clear()
    assert len(PubSubTopicABC.get_registered_topics()) == 2


# ============================================================================
# Tests for PubSubTopicABC - Publishing & Subscribing
# ============================================================================

def test_topic_publish_and_subscribe(test_topic_instance: PubSubTopicABC[TestMessage]) -> None:
    """Test basic publish and subscribe."""
    # Get a subscription
    sub = test_topic_instance.get_subscription()
    
    # Publish a message
    msg = TestMessage(value=42)
    test_topic_instance.publish(message=msg)
    
    # Should receive the message
    received = sub.get(timeout=1)
    assert isinstance(received, TestMessage)
    assert received.value == 42


def test_topic_multiple_subscriptions(test_topic_instance: PubSubTopicABC[TestMessage]) -> None:
    """Test multiple subscriptions receive the same message."""
    sub1 = test_topic_instance.get_subscription()
    sub2 = test_topic_instance.get_subscription()
    sub3 = test_topic_instance.get_subscription()
    
    msg = TestMessage(value=99)
    test_topic_instance.publish(message=msg)
    
    # All subscriptions should receive the message
    for sub in [sub1, sub2, sub3]:
        received = sub.get(timeout=1)
        assert received.value == 99


def test_topic_publish_wrong_message_type(test_topic_instance: PubSubTopicABC[TestMessage]) -> None:
    """Test that publishing wrong message type raises TypeError."""
    wrong_msg = AnotherTestMessage(text="wrong")
    
    with pytest.raises(TypeError, match="Message must be of type TestMessage"):
        test_topic_instance.publish(message=wrong_msg)  # type: ignore


def test_topic_publication_queue(test_topic_instance: PubSubTopicABC[TestMessage]) -> None:
    """Test that messages are also put in the publication queue."""
    msg = TestMessage(value=123)
    test_topic_instance.publish(message=msg)
    
    # Should be in the publication queue
    received = test_topic_instance.publication.get(timeout=1)
    assert received.value == 123


def test_topic_empty_subscriptions(test_topic_instance: PubSubTopicABC[TestMessage]) -> None:
    """Test that subscription queues are empty before publishing."""
    sub = test_topic_instance.get_subscription()
    
    # Should be empty
    with pytest.raises(Empty):
        sub.get(timeout=0.1)


def test_topic_close(test_topic_instance: PubSubTopicABC[TestMessage]) -> None:
    """Test closing a topic."""
    sub1 = test_topic_instance.get_subscription()
    sub2 = test_topic_instance.get_subscription()
    
    assert len(test_topic_instance.subscriptions) == 2
    
    test_topic_instance.close()
    
    # Subscriptions should be cleared
    assert len(test_topic_instance.subscriptions) == 0


# ============================================================================
# Tests for create_topic Factory
# ============================================================================

def test_create_topic_basic() -> None:
    """Test create_topic factory creates a valid topic class."""
    TestTopic = create_topic(message_type=TestMessage)
    
    # Should be a class, not an instance
    assert isinstance(TestTopic, type)
    
    # Should be subclass of PubSubTopicABC
    assert issubclass(TestTopic, PubSubTopicABC)
    
    # Should have correct message_type
    instance = TestTopic()
    assert instance.message_type == TestMessage


def test_create_topic_naming() -> None:
    """Test that create_topic generates appropriate names."""
    TestTopic = create_topic(message_type=TestMessage)
    
    # Should replace 'Message' with 'Topic'
    assert TestTopic.__name__ == "TestTopic"


def test_create_topic_with_custom_publication_factory() -> None:
    """Test create_topic with custom publication factory."""
    custom_queue_created = False
    
    def custom_factory():
        nonlocal custom_queue_created
        custom_queue_created = True
        return Queue()
    
    TestTopic = create_topic(
        message_type=TestMessage,
        publication_factory=custom_factory
    )
    
    # Creating an instance should use the custom factory
    instance = TestTopic()
    assert custom_queue_created


# ============================================================================
# Tests for PubSubTopicManager
# ============================================================================

def test_manager_creation() -> None:
    """Test manager creation and auto-instantiation of topics."""
    # Create some topics
    TestTopic1 = create_topic(message_type=TestMessage)
    TestTopic2 = create_topic(message_type=AnotherTestMessage)
    
    # Create manager
    manager = PubSubTopicManager.create()
    
    # Should have instantiated all registered topics
    assert TestTopic1 in manager.topics
    assert TestTopic2 in manager.topics
    assert isinstance(manager.topics[TestTopic1], TestTopic1)
    assert isinstance(manager.topics[TestTopic2], TestTopic2)


def test_manager_get_subscription() -> None:
    """Test getting subscriptions through manager."""
    TestTopic = create_topic(message_type=TestMessage)
    manager = PubSubTopicManager.create()
    
    # Get subscription
    sub = manager.get_subscription(topic_type=TestTopic)
    
    # Should be a valid queue
    assert sub is not None


def test_manager_get_subscription_unknown_topic() -> None:
    """Test getting subscription for unknown topic raises error."""
    TestTopic = create_topic(message_type=TestMessage)
    manager = PubSubTopicManager.create()
    
    # Create a topic that's not registered with this manager
    class UnregisteredTopic(PubSubTopicABC[TestMessage]):
        message_type: type[TestMessage] = TestMessage
    
    # Remove it from registry to simulate unknown topic
    PubSubTopicABC.topic_registry.discard(UnregisteredTopic)
    
    with pytest.raises(ValueError, match="Unknown topic type"):
        manager.get_subscription(topic_type=UnregisteredTopic)


def test_manager_publish() -> None:
    """Test publishing through manager."""
    TestTopic = create_topic(message_type=TestMessage)
    manager = PubSubTopicManager.create()
    
    sub = manager.get_subscription(topic_type=TestTopic)
    
    msg = TestMessage(value=777)
    manager.publish(topic_type=TestTopic, message=msg)
    
    received = sub.get(timeout=1)
    assert received.value == 777


def test_manager_publish_unknown_topic() -> None:
    """Test publishing to unknown topic raises error."""
    TestTopic = create_topic(message_type=TestMessage)
    manager = PubSubTopicManager.create()
    
    class UnregisteredTopic(PubSubTopicABC[TestMessage]):
        message_type: type[TestMessage] = TestMessage
    
    PubSubTopicABC.topic_registry.discard(UnregisteredTopic)
    
    msg = TestMessage(value=1)
    
    with pytest.raises(ValueError, match="Unknown topic type"):
        manager.publish(topic_type=UnregisteredTopic, message=msg)


def test_manager_close() -> None:
    """Test closing manager closes all topics."""
    TestTopic1 = create_topic(message_type=TestMessage)
    TestTopic2 = create_topic(message_type=AnotherTestMessage)
    manager = PubSubTopicManager.create()
    
    # Get some subscriptions to verify they exist
    sub1 = manager.get_subscription(topic_type=TestTopic1)
    sub2 = manager.get_subscription(topic_type=TestTopic2)
    
    assert len(manager.topics) == 2
    
    manager.close()
    
    # Topics should be cleared
    assert len(manager.topics) == 0


# ============================================================================
# Tests for Pipeline Manager Registry
# ============================================================================

def test_create_pipeline_pubsub_manager() -> None:
    """Test creating pipeline-specific managers."""
    TestTopic = create_topic(message_type=TestMessage)
    
    pipeline_id = "test_pipeline_001"
    manager = create_pipeline_pubsub_manager(pipeline_id=pipeline_id)
    
    # Should be registered
    assert pipeline_id in PIPELINE_PUB_SUB_MANAGERS
    assert PIPELINE_PUB_SUB_MANAGERS[pipeline_id] is manager
    
    # Should have topics
    assert TestTopic in manager.topics


def test_create_pipeline_pubsub_manager_replaces_existing() -> None:
    """Test that creating manager for same pipeline closes old one."""
    TestTopic = create_topic(message_type=TestMessage)
    
    pipeline_id = "test_pipeline_002"
    
    # Create first manager
    manager1 = create_pipeline_pubsub_manager(pipeline_id=pipeline_id)
    sub1 = manager1.get_subscription(topic_type=TestTopic)
    
    # Create second manager for same pipeline
    manager2 = create_pipeline_pubsub_manager(pipeline_id=pipeline_id)
    
    # Should be different instance
    assert manager2 is not manager1
    
    # First manager should be closed
    assert len(manager1.topics) == 0
    
    # Second manager should be active
    assert TestTopic in manager2.topics


def test_multiple_pipeline_managers() -> None:
    """Test multiple pipeline managers can coexist."""
    TestTopic = create_topic(message_type=TestMessage)
    
    manager1 = create_pipeline_pubsub_manager(pipeline_id="pipeline_a")
    manager2 = create_pipeline_pubsub_manager(pipeline_id="pipeline_b")
    
    # Both should be registered
    assert "pipeline_a" in PIPELINE_PUB_SUB_MANAGERS
    assert "pipeline_b" in PIPELINE_PUB_SUB_MANAGERS
    
    # Both should be independent
    assert manager1 is not manager2
    
    # Both should have the topic
    assert TestTopic in manager1.topics
    assert TestTopic in manager2.topics


# ============================================================================
# Integration Tests
# ============================================================================

def test_full_pubsub_workflow() -> None:
    """Test a complete pub/sub workflow."""
    # Create message types and topics
    TestTopic = create_topic(message_type=TestMessage)
    AnotherTopic = create_topic(message_type=AnotherTestMessage)
    
    # Create manager
    manager = PubSubTopicManager.create()
    
    # Get subscriptions
    sub1 = manager.get_subscription(topic_type=TestTopic)
    sub2 = manager.get_subscription(topic_type=TestTopic)
    sub_other = manager.get_subscription(topic_type=AnotherTopic)
    
    # Publish messages
    manager.publish(topic_type=TestTopic, message=TestMessage(value=100))
    manager.publish(topic_type=TestTopic, message=TestMessage(value=200))
    manager.publish(topic_type=AnotherTopic, message=AnotherTestMessage(text="hello"))
    
    # Verify subscriptions received correct messages
    assert sub1.get(timeout=1).value == 100
    assert sub1.get(timeout=1).value == 200
    
    assert sub2.get(timeout=1).value == 100
    assert sub2.get(timeout=1).value == 200
    
    assert sub_other.get(timeout=1).text == "hello"
    
    # Queues should now be empty
    with pytest.raises(Empty):
        sub1.get(timeout=0.1)
    with pytest.raises(Empty):
        sub_other.get(timeout=0.1)
    
    # Clean up
    manager.close()


def test_multiple_message_types_isolated() -> None:
    """Test that different message types don't interfere."""
    TestTopic = create_topic(message_type=TestMessage)
    AnotherTopic = create_topic(message_type=AnotherTestMessage)
    
    manager = PubSubTopicManager.create()
    
    test_sub = manager.get_subscription(topic_type=TestTopic)
    another_sub = manager.get_subscription(topic_type=AnotherTopic)
    
    # Publish to different topics
    manager.publish(topic_type=TestTopic, message=TestMessage(value=42))
    manager.publish(topic_type=AnotherTopic, message=AnotherTestMessage(text="world"))
    
    # Each subscription should only receive its own messages
    test_msg = test_sub.get(timeout=1)
    assert isinstance(test_msg, TestMessage)
    assert test_msg.value == 42
    
    another_msg = another_sub.get(timeout=1)
    assert isinstance(another_msg, AnotherTestMessage)
    assert another_msg.text == "world"
    
    # Queues should be empty
    with pytest.raises(Empty):
        test_sub.get(timeout=0.1)
    with pytest.raises(Empty):
        another_sub.get(timeout=0.1)


# ============================================================================
# Edge Cases & Error Handling
# ============================================================================

def test_publish_before_subscription() -> None:
    """Test that messages published before subscription are not received."""
    TestTopic = create_topic(message_type=TestMessage)
    manager = PubSubTopicManager.create()
    
    # Publish before subscribing
    manager.publish(topic_type=TestTopic, message=TestMessage(value=1))
    
    # Now subscribe
    sub = manager.get_subscription(topic_type=TestTopic)
    
    # Publish after subscribing
    manager.publish(topic_type=TestTopic, message=TestMessage(value=2))
    
    # Should only receive the second message
    received = sub.get(timeout=1)
    assert received.value == 2
    
    # Queue should be empty
    with pytest.raises(Empty):
        sub.get(timeout=0.1)


def test_topic_instance_isolation() -> None:
    """Test that different instances of same topic class are isolated."""
    TestTopic = create_topic(message_type=TestMessage)
    
    instance1 = TestTopic()
    instance2 = TestTopic()
    
    sub1 = instance1.get_subscription()
    sub2 = instance2.get_subscription()
    
    # Publish to instance1
    instance1.publish(message=TestMessage(value=111))
    
    # Only sub1 should receive
    assert sub1.get(timeout=1).value == 111
    
    with pytest.raises(Empty):
        sub2.get(timeout=0.1)
