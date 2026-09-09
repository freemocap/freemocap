"""Tracker/model integration supports head-only evidence without fabricating contacts."""

from dataclasses import replace

import numpy as np
import pytest
from skellyforge.core.biomechanics.alignment_definition import AlignmentDefinition
from skellyforge.core.biomechanics.body_alignment import BodyAlignmentConfig, estimate_body_alignment
from skellytracker.core.io.tracker_mapping import TrackerMapping

from freemocap.core.reconstruction.alignment_evidence import AlignmentEvidence, AlignmentEvidenceRequest
from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle


def head_request() -> AlignmentEvidenceRequest:
    bundle = build_standard_human_bundle(detector_type="rtmpose")
    names = tuple(bundle.skeleton.segments["skull"].landmarks)
    bundle = replace(bundle, landmark_mapping=TrackerMapping(entries={name: name for name in names}))
    frame = np.stack([bundle.rest_pose.landmark_positions[name].array * 1700.0 for name in names])
    return AlignmentEvidenceRequest(
        bundle=bundle, definition=AlignmentDefinition.from_default_human(skeleton=bundle.skeleton),
        timestamps_seconds=np.linspace(0, 1, 11), keypoint_names=names,
        positions=np.tile(frame, (11, 1, 1)), quality=np.full((11, len(names)), .9), minimum_quality=.5,
    )


def test_head_only_evidence_uses_actual_model_without_inventing_feet() -> None:
    evidence = AlignmentEvidence.collect(request=head_request())
    result = estimate_body_alignment(tracks=evidence.body_tracks, config=BodyAlignmentConfig())
    assert result.anchor_segment == "skull"
    assert result.transform is not None
    assert all(np.all(track.quality == 0) for track in evidence.foot_contacts)
    np.testing.assert_allclose(result.transform.rotation.to_rotation_matrix(), np.eye(3), atol=1e-8)


def test_low_quality_cannot_supply_alignment_pose() -> None:
    request = head_request()
    request.quality[:] = .1
    evidence = AlignmentEvidence.collect(request=request)
    assert all(np.all(track.quality == 0) for track in evidence.body_tracks)


def test_invalid_quality_position_pair_is_rejected() -> None:
    request = head_request()
    positions = request.positions.copy()
    positions[0, 0] = np.nan
    with pytest.raises(ValueError, match="Positive-quality"):
        replace(request, positions=positions)
