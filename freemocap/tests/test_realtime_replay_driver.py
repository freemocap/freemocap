"""The deterministic replay driver must not mistake stale or future output for success."""

from queue import Queue
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage
from freemocap.tests.pipelines.mocks.realtime_driver import drive_realtime_lockstep


def replay(frames):
    queue = Queue()
    for frame in frames:
        queue.put(AggregationNodeOutputMessage(frame_number=frame))
    pipeline = SimpleNamespace(alive=True, aggregation_output_subscription=queue,
                               result_ready_event=Event(), result_consumed_event=Event())
    return drive_realtime_lockstep(pipeline=pipeline, mock_group=Mock(),
                                   num_frames=len(frames), per_frame_timeout=1.0)


@pytest.mark.parametrize("frames", [(1,), (0, 0), (0, 2)])
def test_replay_rejects_skipped_or_duplicate_frames(frames):
    with pytest.raises(AssertionError, match="Expected replay frame"):
        replay(frames)


def test_replay_accepts_exact_frame_sequence():
    result = replay((0, 1, 2))
    assert [output.frame_number for output in result.outputs] == [0, 1, 2]
