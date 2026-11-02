from dataclasses import FrozenInstanceError

import pytest
from pydantic import ValidationError

from freemocap.core.streaming.message_model import FrameMessage
from freemocap.core.streaming.outputs.contracts import OutputSample, StartOutputRequest


def test_acquisition_nanoseconds_remain_exact_owned_provenance():
    capture_ns = 9_007_199_254_740_993
    sample = OutputSample(FrameMessage(frame_number=17), "pipeline-a", capture_ns,
                          (("camera-a", capture_ns), ("camera-b", capture_ns + 2)))
    assert sample.source_timestamp_ns == capture_ns
    assert sample.camera_timestamps_ns[0][1] == capture_ns
    with pytest.raises(FrozenInstanceError):
        sample.source_timestamp_ns = capture_ns + 100_000_000


@pytest.mark.parametrize("patch", [dict(queue_capacity=0), dict(queue_capacity=257),
                                   dict(pipeline_id=""), dict(protocol=""),
                                   dict(send_timestamp=True)])
def test_control_rejects_unbounded_or_unknown_configuration(patch):
    with pytest.raises(ValidationError):
        StartOutputRequest.model_validate({"protocol": "lsl", **patch})


def test_idle_configuration_does_not_require_a_capture_session():
    request = StartOutputRequest(protocol="vmc", pipeline_id="future-source")
    assert request.pipeline_id == "future-source"
    assert request.queue_capacity == 8
