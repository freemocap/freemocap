"""A geometry check obeys policy without discarding a usable camera binding."""

import pytest
from concurrent.futures import Future

from freemocap.core.tasks.calibration.camera_matching.live_matching import LiveGeometryMatcher
from freemocap.core.tasks.calibration.camera_matching.matching_models import (
    AssignmentSearchResult, CameraMatchingConfig, CameraMatchingResult, CameraMatchingStatus,
    MatchingFailurePolicy, ScoredAssignment,
)
from freemocap.tests.calibration.test_calibration_state_latch import build_loaded_tracker


@pytest.mark.parametrize('status', [CameraMatchingStatus.POOR, CameraMatchingStatus.AMBIGUOUS])
def test_continue_preserves_working_binding(status: CameraMatchingStatus) -> None:
    tracker = build_loaded_tracker()
    assert tracker.calibration is not None
    source_ids = tuple(camera.id for camera in tracker.calibration.cameras)
    tracker.bind_live_cameras(live_camera_indices={source: index for index, source in enumerate(source_ids)})
    binding = tracker.binding
    assert tracker.is_applicable()
    tracker.apply_matching(source_ids=source_ids, result=CameraMatchingResult(status=status, assignment=None, fitness=None, search=None), failure_policy=MatchingFailurePolicy.CONTINUE)
    assert tracker.binding is binding
    assert tracker.is_applicable()


def test_stop_policy_raises_on_poor_geometry() -> None:
    tracker = build_loaded_tracker()
    with pytest.raises(ValueError, match='configured failure policy: poor'):
        tracker.apply_matching(source_ids=('cam0', 'cam1', 'cam2'), result=CameraMatchingResult(status=CameraMatchingStatus.POOR, assignment=None, fitness=None, search=None), failure_policy=MatchingFailurePolicy.STOP)


@pytest.mark.parametrize('status,assignment,has_search,expected_change', [
    (CameraMatchingStatus.POOR, (1, 0, 2), True, False),
    (CameraMatchingStatus.AMBIGUOUS, (1, 0, 2), True, False),
    (CameraMatchingStatus.INSUFFICIENT, None, False, False),
    (CameraMatchingStatus.MATCHED, (0, 1, 2), True, False),
    (CameraMatchingStatus.MATCHED, (1, 0, 2), True, True),
    (CameraMatchingStatus.INITIAL_ACCEPTED, (1, 0, 2), False, True),
])
def test_live_matching_reports_actual_assignment_changes(status, assignment, has_search, expected_change):
    tracker = build_loaded_tracker()
    camera_indices = {'cam0': 0, 'cam1': 1, 'cam2': 2}
    matcher = LiveGeometryMatcher(calibration=tracker, camera_indices=camera_indices)
    config = CameraMatchingConfig()
    try:
        matcher.update(observations={}, config=config, elapsed_seconds=0.)
        cache_key = frozenset(('cam0', 'cam1'))
        cached_triangulator = tracker.triangulator
        tracker._subset_triangulator_cache[cache_key] = cached_triangulator
        search = (AssignmentSearchResult(best=ScoredAssignment(camera_indices=assignment, mean_cost=0.),
                                        runner_up=None, complete=True, expanded_nodes=1) if has_search else None)
        result = CameraMatchingResult(status=status, assignment=assignment, fitness=None, search=search)
        matcher._attempt = matcher._lifecycle.begin()
        matcher._future = Future()
        matcher._future.set_result(result)
        assert matcher.update(observations={}, config=config, elapsed_seconds=1.) is expected_change
        if expected_change:
            assert not tracker._subset_triangulator_cache
            assert tracker.binding.by_live_id['cam0'].id == 'cam1'
        else:
            assert tracker._subset_triangulator_cache[cache_key] is cached_triangulator
            assert tracker.binding.by_live_id['cam0'].id == 'cam0'
    finally:
        matcher.close()


def test_matching_reports_recovered_applicability_and_reset_assignment():
    tracker = build_loaded_tracker()
    camera_indices = {'cam0': 0, 'cam1': 1, 'cam2': 2}
    tracker.bind_live_cameras(live_camera_indices=camera_indices)
    tracker._is_valid = False
    result = CameraMatchingResult(status=CameraMatchingStatus.MATCHED, assignment=(0, 1, 2), fitness=None, search=None)
    assert tracker.apply_matching(source_ids=tuple(camera_indices), result=result,
                                  failure_policy=MatchingFailurePolicy.CONTINUE)
    assert tracker.is_applicable()
    assert not tracker.reset_matching(camera_indices=camera_indices)
    remapped = CameraMatchingResult(status=CameraMatchingStatus.MATCHED, assignment=(1, 0, 2), fitness=None, search=None)
    assert tracker.apply_matching(source_ids=tuple(camera_indices), result=remapped,
                                  failure_policy=MatchingFailurePolicy.CONTINUE)
    assert tracker.reset_matching(camera_indices=camera_indices)
    assert tracker.binding.by_live_id['cam0'].id == 'cam0'
