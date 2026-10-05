"""Anchoring changes placement, never dimensions or anatomical joint conventions."""
from dataclasses import replace

import numpy as np
import pytest
from numpy.testing import assert_allclose

from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
from freemocap.core.skeletons.reconstruct_skeleton import reconstruct_skeleton
from freemocap.core.recording.data_descriptors.recording_model import RecordedModel
from freemocap.core.reconstruction.recording_fit import RecordingFitInputs
from freemocap.tests.test_hand_reconstruction_contract import tracked_hands
from freemocap.tests.test_trajectory_products import state_for


def test_skull_stays_anchored_when_hip_evidence_moves_and_survives_missing_body():
    bundle = build_standard_human_bundle(detector_type='rtmpose', anchor_segment_name='skull')
    points = tracked_hands(bundle)
    state = state_for(bundle)
    reconstruct_skeleton(bundle=bundle, state=state, filtered_keypoints=points, compute_center_of_mass=False)
    fit = state.scale_source.current_fit()
    skull_origins = []
    pelvis_origins = []
    for displacement in (0., 35., -30.):
        frame = {name: point.copy() for name, point in points.items()}
        for side in ('left', 'right'):
            frame[f'{side}_hip'] += [displacement, 0., displacement]
        for anchored, results in ((bundle, skull_origins), (replace(bundle, anchor_segment_name='pelvis'), pelvis_origins)):
            result = reconstruct_skeleton(bundle=anchored, state=state_for(bundle, fit), filtered_keypoints=frame, compute_center_of_mass=False)
            results.append(result.segment_origins['skull'])
    assert_allclose(skull_origins, np.repeat([skull_origins[0]], 3, axis=0), atol=1e-9)
    assert np.linalg.norm(pelvis_origins[1] - pelvis_origins[0]) > 1.
    head_only = {name: point for name, point in points.items() if name in ('nose', 'left_ear', 'right_ear', 'left_eye', 'right_eye')}
    result = reconstruct_skeleton(bundle=bundle, state=state_for(bundle, fit), filtered_keypoints=head_only, compute_center_of_mass=False)
    assert 'skull' in result.segment_origins and 'pelvis' not in result.segment_origins
    assert not result.segment_rotations_local  # No anatomical parent pose to reference.
    absent = reconstruct_skeleton(bundle=bundle, state=state_for(bundle, fit), filtered_keypoints={'left_wrist': points['left_wrist']}, compute_center_of_mass=False)
    assert absent.mapped_keypoints and not absent.segment_origins


def test_anchor_is_persisted_but_does_not_change_scale_evidence():
    bundle = build_standard_human_bundle(detector_type='rtmpose')
    skull = replace(bundle, anchor_segment_name='skull')
    models = [RecordedModel.from_bundle(b) for b in (bundle, skull)]
    assert models[0].model_dump() != models[1].model_dump()
    restored = RecordedModel.model_validate_json(models[1].model_dump_json()).to_bundle()
    assert restored.anchor_segment_name == 'skull'
    fits = [RecordingFitInputs.from_points(names=('point',), values=np.ones((2, 1, 3)), model=m) for m in models]
    assert fits[0] == fits[1]
    with pytest.raises(ValueError, match='Unknown reconstruction anchor'):
        replace(bundle, anchor_segment_name='nose')
