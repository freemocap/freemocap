"""Independent connections observe the same newest pipeline output."""

from queue import Queue
from threading import Event
from unittest.mock import Mock

from freemocap.core.pipeline.realtime.realtime_pipeline import RealtimePipeline
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage


def test_connections_do_not_steal_each_others_frames() -> None:
    pipeline = Mock(spec=RealtimePipeline)
    pipeline.alive = True
    pipeline._latest_aggregation_output = None
    pipeline.aggregation_output_subscription = Queue()
    pipeline.result_ready_event = Event()
    pipeline.result_consumed_event = Event()
    first = AggregationNodeOutputMessage(frame_number=10)
    pipeline.aggregation_output_subscription.put(first)
    pipeline.result_ready_event.set()
    for _ in range(3):
        assert RealtimePipeline.get_latest_aggregator_output(pipeline, if_newer_than=9) is first
    assert pipeline.result_consumed_event.is_set()
    assert RealtimePipeline.get_latest_aggregator_output(pipeline, if_newer_than=10) is None
    second = AggregationNodeOutputMessage(frame_number=11)
    pipeline.aggregation_output_subscription.put(second)
    assert RealtimePipeline.get_latest_aggregator_output(pipeline, if_newer_than=10) is second
    assert RealtimePipeline.get_latest_aggregator_output(pipeline, if_newer_than=9) is second
