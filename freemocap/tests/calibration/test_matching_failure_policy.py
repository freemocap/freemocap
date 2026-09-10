"""A geometry check obeys policy without discarding a usable camera binding."""

import pytest

from freemocap.core.tasks.calibration.camera_matching.matching_models import CameraMatchingResult, CameraMatchingStatus, MatchingFailurePolicy
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
