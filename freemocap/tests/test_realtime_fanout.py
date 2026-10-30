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
    pipeline.result_consumed_event.clear()
    pipeline.result_ready_event.set()
    assert RealtimePipeline.get_latest_aggregator_output(pipeline, if_newer_than=10) is second
    assert RealtimePipeline.get_latest_aggregator_output(pipeline, if_newer_than=9) is second


def test_publication_cannot_be_acknowledged_before_producer_sets_ready() -> None:
    pipeline = Mock(spec=RealtimePipeline)
    pipeline.alive = True
    previous = AggregationNodeOutputMessage(frame_number=9)
    pipeline._latest_aggregation_output = previous
    pipeline.aggregation_output_subscription = Queue()
    pipeline.result_ready_event = Event()
    pipeline.result_consumed_event = Event()
    pipeline.result_consumed_event.set()
    current = AggregationNodeOutputMessage(frame_number=10)
    pipeline.aggregation_output_subscription.put(current)
    # A connection arrives between the producer's queue publication and event updates.
    assert RealtimePipeline.get_latest_aggregator_output(pipeline, if_newer_than=8) is previous
    assert pipeline.aggregation_output_subscription.qsize() == 1
    pipeline.result_consumed_event.clear()
    pipeline.result_ready_event.set()
    assert RealtimePipeline.get_latest_aggregator_output(pipeline, if_newer_than=9) is current
    assert pipeline.result_consumed_event.is_set()
    assert not pipeline.result_ready_event.is_set()
