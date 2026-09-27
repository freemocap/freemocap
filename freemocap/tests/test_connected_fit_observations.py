"""Existing tracker mappings feed connected targets without duplicate evidence."""

from dataclasses import replace

import numpy as np
import pytest
from skellytracker.core.io.tracker_mapping import TrackerMapping
from skellyforge.core.skeleton.chain.synthesis import synthesize_pose
from skellyforge.core.math.geometry.rotation_quaternion import RotationQuaternion

from freemocap.core.reconstruction.connected_fit_observations import (
    connected_fit_observations,
)
from freemocap.core.recording.data_descriptors.recording_model import RecordedModel
from freemocap.core.skeletons.standard_human_skeleton import (
    build_standard_human_bundle,
    STANDARD_HUMAN_UPPER_BODY_FIT_LANDMARKS,
)


@pytest.fixture(params=["rtmpose", "mediapipe"])
def bundle(request):
    original = build_standard_human_bundle(detector_type=request.param)
    # Exercise the saved definitions used by recording replay, not YAML reloads.
    model = RecordedModel.from_bundle(original)
    return RecordedModel.model_validate_json(model.model_dump_json()).to_bundle()


def test_upper_body_selection_matches_connected_geometry_for_both_trackers(bundle):
    skeleton = bundle.skeleton
    rotations = {
        joint.name: (
            RotationQuaternion.from_rotation_vector(
                rotation_vector=np.array([0.2, -0.1, 0.3])
            )
            * bundle.rest_pose.relative_orientations[joint.child.name]
        )
        for joint in skeleton.joints.values()
    }
    _, _, predicted = synthesize_pose(
        skeleton=skeleton,
        joint_relative_orientations=rotations,
        segment_scales={name: 1700.0 for name in skeleton.segments},
    )
    # Synthetic exact inputs check the cross-repository correspondence, not
    # anatomical accuracy, real-data fit quality, or solver observability.
    source_to_landmark = {
        "left_hip": "left_hip_socket",
        "right_hip": "right_hip_socket",
        "left_shoulder": "left_acromion",
        "right_shoulder": "right_acromion",
        "left_elbow": "left_elbow",
        "right_elbow": "right_elbow",
        "left_wrist": "left_wrist",
        "right_wrist": "right_wrist",
        "left_ear": "left_ear",
        "right_ear": "right_ear",
        "nose": "nose",
    }
    result = connected_fit_observations(
        bundle=bundle,
        keypoints={
            source: predicted[name].array for source, name in source_to_landmark.items()
        },
        landmark_tolerances={
            name: 1.0 for name in STANDARD_HUMAN_UPPER_BODY_FIT_LANDMARKS
        },
    )
    assert result.source_keypoints == {
        name: source for source, name in source_to_landmark.items()
    }
    assert len(result.targets) == 11
    for name, target in result.targets.items():
        np.testing.assert_array_equal(target.position.array, predicted[name].array)
    # Alternate names at connected joints do not supply additional evidence.
    for side in ("left", "right"):
        np.testing.assert_allclose(
            predicted[f"{side}_acromion"].array,
            predicted[f"{side}_shoulder"].array,
            atol=1e-10,
        )


def test_targets_keep_original_coordinates_and_source_identity(bundle):
    points = {
        "left_shoulder": np.array([123.0, -42.0, 987.0]),
        "left_elbow": np.array([200.0, 10.0, 800.0]),
    }
    result = connected_fit_observations(
        bundle=bundle,
        keypoints=points,
        landmark_tolerances={"left_acromion": 5.0, "left_elbow": 8.0},
    )
    assert result.source_keypoints == {
        "left_acromion": "left_shoulder",
        "left_elbow": "left_elbow",
    }
    mapped = bundle.landmark_mapping.apply(points)
    for name, target in result.targets.items():
        np.testing.assert_array_equal(target.position.array, mapped[name])
    assert result.targets["left_elbow"].tolerance == 8.0
    points["left_shoulder"][:] = 0
    np.testing.assert_array_equal(
        result.targets["left_acromion"].position.array, [123.0, -42.0, 987.0]
    )


def test_duplicate_evidence_rejected_even_when_missing(bundle):
    with pytest.raises(ValueError, match="reuse keypoint 'left_shoulder'"):
        connected_fit_observations(
            bundle=bundle,
            keypoints={},
            landmark_tolerances={"left_acromion": 5.0, "left_shoulder": 5.0},
        )


@pytest.mark.parametrize("name", ["neck_center", "left_sternoclavicular"])
def test_constructed_targets_are_not_silently_independent(bundle, name):
    with pytest.raises(ValueError, match="requires a direct"):
        connected_fit_observations(
            bundle=bundle, keypoints={}, landmark_tolerances={name: 5.0}
        )


def test_missing_observations_preserve_selected_source_records(bundle):
    result = connected_fit_observations(
        bundle=bundle,
        keypoints={"left_shoulder": np.array([1.0, np.nan, 3.0])},
        landmark_tolerances={"left_acromion": 5.0, "left_elbow": 5.0},
    )
    assert result.targets == {}
    assert result.source_keypoints == {
        "left_acromion": "left_shoulder",
        "left_elbow": "left_elbow",
    }


@pytest.mark.parametrize("position", [[1.0, 2.0], [1.0, np.inf, 3.0]])
def test_invalid_observations_fail(bundle, position):
    with pytest.raises(ValueError, match="XYZ point"):
        connected_fit_observations(
            bundle=bundle,
            keypoints={"left_shoulder": np.array(position)},
            landmark_tolerances={"left_acromion": 5.0},
        )


@pytest.mark.parametrize("tolerance", [0.0, -1.0, np.nan, np.inf])
def test_invalid_tolerance_fails_even_with_missing_observation(bundle, tolerance):
    with pytest.raises(ValueError, match="finite and positive"):
        connected_fit_observations(
            bundle=bundle,
            keypoints={},
            landmark_tolerances={"left_acromion": tolerance},
        )


@pytest.mark.parametrize("passthrough", [False, True])
def test_prefixed_mapping_uses_full_source_name(bundle, passthrough):
    source = "camera_left_elbow"
    mapping = TrackerMapping(
        entries={} if passthrough else {"left_elbow": "left_elbow"},
        prefix="camera_",
        known_tracker_keypoints={source},
        passthrough_keypoints_as_landmarks=passthrough,
    )
    selected = replace(
        bundle, landmark_mapping=mapping, tracker_keypoint_names=(source,)
    )
    result = connected_fit_observations(
        bundle=selected,
        keypoints={source: np.array([1.0, 2.0, 3.0])},
        landmark_tolerances={"left_elbow": 5.0},
    )
    assert result.source_keypoints == {"left_elbow": source}
    np.testing.assert_array_equal(
        result.targets["left_elbow"].position.array, [1.0, 2.0, 3.0]
    )
