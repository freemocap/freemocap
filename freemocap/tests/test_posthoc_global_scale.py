"""Every batch frame uses the complete recording's scale evidence."""

import numpy as np

from freemocap.core.reconstruction.posthoc_reconstruction import (
    reconstruct_skeletons_for_recording,
)
from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
from freemocap.tests.test_model_scale_in_the_loop import _standing_keypoints


def test_early_noisy_frames_use_the_same_fit_as_late_frames() -> None:
    points = _standing_keypoints()
    names = tuple(points)
    frame = np.stack(list(points.values()))
    recording = np.stack(
        [frame * scale for scale in (1.5, 1.4, 1.0, 1.0, 1.0, 1.0, 1.0)]
    )
    bundle = build_standard_human_bundle(detector_type="rtmpose")
    results = reconstruct_skeletons_for_recording(
        bundles=[bundle],
        keypoint_names=names,
        keypoints_3d=recording,
        frame_count=len(recording),
        compute_center_of_mass=True,
        timing=PosthocTimingReport(),
    )[bundle.model_id]
    assert all(result is not None for result in results)
    scales = [result.fitted_scale_mm for result in results if result is not None]
    assert scales[0] is not None
    assert len(set(scales)) == 1
    lengths = [result.segment_lengths for result in results if result is not None]
    assert all(value == lengths[0] for value in lengths)


def test_all_missing_recording_remains_missing() -> None:
    names = tuple(_standing_keypoints())
    bundle = build_standard_human_bundle(detector_type="rtmpose")
    results = reconstruct_skeletons_for_recording(
        bundles=[bundle],
        keypoint_names=names,
        keypoints_3d=np.full((2, len(names), 3), np.nan),
        frame_count=2,
        compute_center_of_mass=True,
        timing=PosthocTimingReport(),
    )
    assert results[bundle.model_id] == [None, None]
