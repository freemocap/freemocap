"""Retry ownership and stale calibration generations."""

import pytest

from freemocap.core.tasks.calibration.camera_matching.matching_lifecycle import MatchingLifecycle, MatchingLifecycleState
from freemocap.core.tasks.calibration.camera_matching.matching_models import CameraMatchingResult, CameraMatchingStatus


@pytest.mark.parametrize("status", [CameraMatchingStatus.POOR, CameraMatchingStatus.AMBIGUOUS, CameraMatchingStatus.SEARCH_LIMIT])
def test_failed_search_latches_until_reset(status: CameraMatchingStatus) -> None:
    lifecycle = MatchingLifecycle()
    attempt = lifecycle.begin()
    lifecycle.finish(attempt=attempt, result=CameraMatchingResult(status=status, assignment=None, fitness=None, search=None))
    assert lifecycle.state is MatchingLifecycleState.SUSPENDED
    with pytest.raises(ValueError, match="suspended"):
        lifecycle.begin()
    lifecycle.reset()
    assert lifecycle.begin().generation != attempt.generation


def test_insufficient_tracks_allow_more_collection() -> None:
    lifecycle = MatchingLifecycle()
    lifecycle.finish(attempt=lifecycle.begin(), result=CameraMatchingResult(
        status=CameraMatchingStatus.INSUFFICIENT, assignment=None, fitness=None, search=None,
    ))
    assert lifecycle.state is MatchingLifecycleState.COLLECTING
    lifecycle.begin()


def test_old_result_cannot_replace_new_generation_or_its_active_attempt() -> None:
    lifecycle = MatchingLifecycle()
    old = lifecycle.begin()
    lifecycle.reset()
    current = lifecycle.begin()
    result = CameraMatchingResult(status=CameraMatchingStatus.MATCHED, assignment=(1, 0), fitness=None, search=None)
    assert not lifecycle.finish(attempt=old, result=result)
    assert lifecycle.state is MatchingLifecycleState.RUNNING
    assert lifecycle.finish(attempt=current, result=result)


def test_concurrent_submission_is_rejected() -> None:
    lifecycle = MatchingLifecycle()
    lifecycle.begin()
    with pytest.raises(ValueError, match="running"):
        lifecycle.begin()


def test_missing_track_window_preserves_previous_assignment() -> None:
    lifecycle = MatchingLifecycle()
    accepted = CameraMatchingResult(status=CameraMatchingStatus.MATCHED, assignment=(1, 0), fitness=None, search=None)
    lifecycle.finish(attempt=lifecycle.begin(), result=accepted)
    lifecycle.finish(attempt=lifecycle.begin(), result=CameraMatchingResult(
        status=CameraMatchingStatus.INSUFFICIENT, assignment=None, fitness=None, search=None,
    ))
    assert lifecycle.result is accepted
