import pickle
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from freemocap.pubsub.pubsub_topics import (
    CalibrationRecordingStateMessage,
    CalibrationRecordingStateTopic,
)
from freemocap.pubsub.pubsub_abcs import PubSubTopicABC


def test_message_roundtrip():
    """CalibrationRecordingStateMessage survives pickle roundtrip."""
    info = RecordingInfo.create_temp()
    msg = CalibrationRecordingStateMessage(recording_info=info, is_active=True)

    reloaded = pickle.loads(pickle.dumps(msg))

    assert reloaded.recording_info.recording_name == info.recording_name
    assert reloaded.is_active is True


def test_message_defaults():
    """Default values are sensible."""
    msg = CalibrationRecordingStateMessage()

    assert msg.is_active is False


def test_topic_is_registered():
    """CalibrationRecordingStateTopic is auto-discovered."""
    registered = PubSubTopicABC.get_registered_topics()
    assert CalibrationRecordingStateTopic in registered


def test_topic_message_type():
    """Topic wraps the correct message type."""
    assert CalibrationRecordingStateTopic.message_type is CalibrationRecordingStateMessage
