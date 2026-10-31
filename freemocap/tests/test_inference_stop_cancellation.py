from concurrent.futures import CancelledError, Future
from types import SimpleNamespace

import pytest

from freemocap.core.pipeline.realtime.realtime_skeleton_inference_node import _await_inference_result


@pytest.mark.parametrize(('running', 'stopping'), [(False, False), (True, True)])
def test_expected_pipeline_cancellation_finishes_without_a_worker_error(running, stopping):
    result = Future()
    result.set_exception(CancelledError('Pipeline stopped during inference'))
    assert _await_inference_result(result, SimpleNamespace(should_continue=running), SimpleNamespace(value=stopping)) is None


def test_unexpected_inference_cancellation_is_not_hidden():
    result = Future()
    result.cancel()
    with pytest.raises(CancelledError):
        _await_inference_result(result, SimpleNamespace(should_continue=True), SimpleNamespace(value=False))
