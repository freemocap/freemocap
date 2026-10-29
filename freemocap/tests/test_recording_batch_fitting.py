"""Recording fitting retains scalar hydration evidence, including missing data."""
from dataclasses import replace
import numpy as np
import pytest
from freemocap.tests.test_saved_reconstruction import saved_request
from freemocap.core.recording.result_processing.saved_reconstruction import read_saved_reconstruction
from freemocap.core.reconstruction.posthoc_reconstruction import fit_skeletons_for_recording
from freemocap.tests.recording_tensor_assertions import _finite_frame_points
from freemocap.core.skeletons.reconstruction_state import streaming_model_scale_source
from skellyforge.core.math.geometry.spatial_vectors import Point
from skellyforge.core.skeleton.pose.hydration import hydrate_skeleton

@pytest.mark.parametrize('missing', [False, True])
def test_batch_fit_preserves_scalar_evidence(saved_request, missing):
    request = read_saved_reconstruction(saved_request).numerical_input
    if missing:
        request = replace(request, keypoints_3d=np.full_like(request.keypoints_3d, np.nan), measured_support=None)
    actual = fit_skeletons_for_recording(request)
    for bundle in request.bundles:
        source = streaming_model_scale_source(window_frames=request.frame_count)(bundle)
        for frame in request.scale_points:
            mapped = bundle.landmark_mapping.apply(tracker_positions=_finite_frame_points(frame=frame, point_names=request.keypoint_names))
            if mapped:
                source.observe_pose(pose=hydrate_skeleton(skeleton=bundle.skeleton,
                    observed={name: Point.from_array(values=value) for name,value in mapped.items()}, require_all=False))
        expected = source.current_fit() if source.has_model_scale else None
        fitted = actual[bundle.model_id].fit
        if expected is None:
            assert fitted is None
        else:
            assert fitted.measured_segment_names == expected.measured_segment_names
            assert fitted.voting_segment_names == expected.voting_segment_names
            np.testing.assert_allclose(fitted.fitted_scale, expected.fitted_scale, rtol=1e-8, atol=1e-6)
            np.testing.assert_allclose(list(fitted.segment_scales.values()), list(expected.segment_scales.values()), rtol=1e-8, atol=1e-6)
