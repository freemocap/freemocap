"""Observation-frame definitions survive recording JSON and identify fit inputs."""

from copy import deepcopy

import numpy as np
import pytest

from freemocap.core.recording.data_descriptors.recording_model import RecordedModel
from freemocap.core.recording.result_processing.input_signatures import definition_signature
from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
from skellyforge.core.math.geometry.spatial_vectors import Point
from skellyforge.core.skeleton.pose.hydration import hydrate_segment


def human_model():
    return RecordedModel.from_bundle(build_standard_human_bundle(detector_type="rtmpose"))


def test_recording_json_preserves_observation_frames_and_poses():
    original = human_model()
    restored = RecordedModel.model_validate_json(original.model_dump_json())
    before, after = original.to_bundle(), restored.to_bundle()
    assert definition_signature(original) == definition_signature(restored)
    points = {n: Point.from_array(values=np.array(p, dtype=float)) for n, p in {
        "pelvis_origin": [0, 0, 0], "left_hip_socket": [-150, 10, 0],
        "right_hip_socket": [150, -10, 0], "chest_center": [20, -15, 300],
        "neck_center": [-10, 30, 600], "left_acromion": [-180, 15, 675],
        "right_acromion": [160, 45, 525],
    }.items()}
    for name in ("pelvis", "thoracic"):
        assert after.skeleton.segments[name].observation_frame == before.skeleton.segments[name].observation_frame
        a = hydrate_segment(segment=before.skeleton.segments[name], observed=points)
        b = hydrate_segment(segment=after.skeleton.segments[name], observed=points)
        assert a.orientation.is_same_rotation(other=b.orientation)
        assert a.solved_by == b.solved_by
        assert a.scale_estimate == b.scale_estimate
        np.testing.assert_array_equal(a.origin.array, b.origin.array)


def test_legacy_model_fingerprint_survives_loading_without_inventing_frames():
    legacy = human_model().model_dump(mode="json")
    for segment in legacy["skeleton"]["segments"]:
        segment.pop("observation_frame", None)
    expected = definition_signature(legacy)
    loaded = RecordedModel.model_validate(legacy)
    assert loaded.model_dump(mode="json") == legacy
    assert definition_signature(loaded) == expected
    assert all(s.observation_frame is None for s in loaded.to_bundle().skeleton.segments.values())
    assert definition_signature(human_model()) != expected


def test_changing_only_observation_frame_invalidates_model_signature():
    original = human_model()
    changed = deepcopy(original.model_dump(mode="json"))
    segment = next(s for s in changed["skeleton"]["segments"] if s["name"] == "thoracic")
    segment["observation_frame"]["primary_point"] = "pelvis_origin"
    assert definition_signature(RecordedModel.model_validate(changed)) != definition_signature(original)


@pytest.mark.parametrize("detector_type", ["rtmpose", "mediapipe"])
def test_recording_preserves_mapping_evaluation_and_landmark_attachments(detector_type):
    """Replay keeps both sides of the existing keypoint-to-model correspondence."""
    before = build_standard_human_bundle(detector_type=detector_type)
    recorded = RecordedModel.from_bundle(before)
    after = RecordedModel.model_validate_json(recorded.model_dump_json()).to_bundle()
    assert after.landmark_mapping.mapping_snapshots() == before.landmark_mapping.mapping_snapshots()

    # Asymmetric inputs exercise offset frames as well as direct/weighted forms.
    # These are serialization checks, not claims of anatomical accuracy.
    rng = np.random.default_rng(42)
    positions = {
        name: rng.normal(size=3) * 300
        for name in before.tracker_keypoint_names
    }
    for inputs in (positions, {n: p for i, (n, p) in enumerate(positions.items()) if i % 3}):
        expected = before.landmark_mapping.apply(inputs)
        actual = after.landmark_mapping.apply(inputs)
        assert actual.keys() == expected.keys()
        for name in expected:
            np.testing.assert_array_equal(actual[name], expected[name])
            original_landmark = before.skeleton.landmarks[name]
            restored_landmark = after.skeleton.landmarks[name]
            assert restored_landmark.segment == original_landmark.segment
            np.testing.assert_array_equal(
                restored_landmark.local_position.array,
                original_landmark.local_position.array,
            )
