"""Batch preparation preserves the scalar path across gaps and chunk boundaries."""
from dataclasses import fields, is_dataclass
from freemocap.tests.recording_tensor_assertions import reconstruction_frame, _finite_frame_points

import numpy as np
import pytest

from freemocap.core.reconstruction.posthoc_reconstruction import (
    fit_skeletons_for_recording, reconstruct_skeletons_with_fits,
)
from freemocap.core.reconstruction.recording_reconstruction import RecordingReconstructionInput
from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.skeletons.reconstruct_skeleton import reconstruct_skeleton
from freemocap.core.skeletons.skeleton_reconstruction import SkeletonReconstruction
from freemocap.core.skeletons.reconstruction_state import FrozenModelScale, build_reconstruction_states
from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
from freemocap.tests.test_hand_reconstruction_contract import tracked_hands
from freemocap.tests.test_trajectory_products import state_for


def assert_reconstruction_equal(expected, actual):
    if is_dataclass(expected):
        for field in fields(expected):
            assert_reconstruction_equal(getattr(expected, field.name), getattr(actual, field.name))
    elif isinstance(expected, dict):
        assert expected.keys() == actual.keys()
        for name in expected:
            assert_reconstruction_equal(expected[name], actual[name])
    elif isinstance(expected, (tuple, list, np.ndarray, float, np.floating)):
        np.testing.assert_allclose(actual, expected, atol=1e-6, rtol=1e-8, equal_nan=True)
    else:
        assert expected == actual


@pytest.mark.parametrize('tracker', ['rtmpose', 'mediapipe'])
def test_frame_chunks_match_scalar_reconstruction(tracker, monkeypatch):
    bundle = build_standard_human_bundle(detector_type=tracker)
    points = tracked_hands(bundle)
    names = tuple(points)
    values = np.tile(np.array(list(points.values())), (260, 1, 1))
    values[254:257] = np.nan  # Empty data crosses the 256-frame chunk boundary.
    values[258, :5] = np.nan  # Partial reentry must retain its actual coverage.
    request = RecordingReconstructionInput(bundles=(bundle,), keypoint_names=names,
        keypoints_3d=values, compute_center_of_mass=True, timing=PosthocTimingReport())
    fits = fit_skeletons_for_recording(request)
    def forbid_frame_result(*args, **kwargs):
        raise AssertionError("Recording numerical outputs must not materialize per-frame result dictionaries")
    with monkeypatch.context() as boundary:
        boundary.setattr(SkeletonReconstruction, "__init__", forbid_frame_result)
        actual = reconstruct_skeletons_with_fits(request=request, fits=fits)[bundle.model_id]
    state = state_for(bundle, fits[bundle.model_id].fit)
    for index, frame in enumerate(values):
        points = _finite_frame_points(frame=frame, point_names=names)
        if not points:
            state.reset()
        expected = reconstruct_skeleton(bundle=bundle, state=state,
            filtered_keypoints=points, compute_center_of_mass=True)
        assert_reconstruction_equal(expected, reconstruction_frame(actual, index, bundle))


def test_absent_fit_and_empty_observations_remain_absent():
    bundle = build_standard_human_bundle(detector_type='rtmpose')
    points = tracked_hands(bundle)
    names = tuple(points)
    values = np.full((2, len(names), 3), np.nan)
    values[1, 0] = list(points.values())[0]
    request = RecordingReconstructionInput(bundles=(bundle,), keypoint_names=names,
        keypoints_3d=values, compute_center_of_mass=True, timing=PosthocTimingReport())
    fits = fit_skeletons_for_recording(request)
    assert fits[bundle.model_id].fit is None
    result = reconstruct_skeletons_with_fits(request=request, fits=fits)[bundle.model_id]
    assert reconstruction_frame(result, 0, bundle) is None
    scalar_state = build_reconstruction_states(bundles=(bundle,),
        scale_source_for=lambda _: FrozenModelScale(fit=None))[bundle.model_id]
    expected = reconstruct_skeleton(bundle=bundle, state=scalar_state,
        filtered_keypoints=_finite_frame_points(frame=values[1], point_names=names), compute_center_of_mass=True)
    assert_reconstruction_equal(expected, reconstruction_frame(result, 1, bundle))

