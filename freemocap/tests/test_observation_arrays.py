"""Dense observation access preserves Tracker identity and numerical semantics."""
from unittest.mock import patch

import numpy as np
import pytest
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellytracker.core.data_primitives.observation import Observation, StageObservation

from freemocap.core.tracking.observation_arrays import (
    observation_arrays, observation_point_names, point_selection,
)
from freemocap.core.tracking.observation_buffer import ObservationBuffer
from freemocap.core.tasks.calibration.camera_matching.observation_sampling import select_matching_point_names


def observation(frame=0, names=("second", "first"), confidence=(0.8, 0.5)):
    return Observation(frame_number=frame, image_size=(120, 160), stages={
        "body": StageObservation(name="body", keypoints=Keypoints(names=names,
            xyz=np.arange(len(names) * 3, dtype=np.float64).reshape(len(names), 3),
            visibility=np.asarray(confidence, dtype=np.float64)))})


def test_single_stage_borrows_current_arrays_and_never_calls_flattening():
    item = observation()
    with patch.object(Observation, "to_keypoints", side_effect=AssertionError("Rebuilt Keypoints")):
        first = observation_arrays(item)
        assert first.point_names == ("body.second", "body.first")
        assert first.coordinate_values is item.stages["body"].keypoints.xyz
        assert first.confidence_scores is item.stages["body"].keypoints.visibility
        item.stages["body"].keypoints.xyz = np.ones_like(first.coordinate_values)
        second = observation_arrays(item)
        assert second.coordinate_values is item.stages["body"].keypoints.xyz
        assert second.point_names is first.point_names
        assert not np.shares_memory(first.coordinate_values, second.coordinate_values)


def test_nested_stage_order_and_values_match_tracker_without_keypoint_objects():
    item = observation()
    item.stages["body"].children["hand"] = StageObservation(name="hand", keypoints=Keypoints(
        names=("finger",), xyz=np.array([[9., 8., 7.]]), visibility=np.array([0.7])))
    expected = item.to_keypoints()
    with patch.object(Observation, "to_keypoints", side_effect=AssertionError("Rebuilt Keypoints")):
        result = observation_arrays(item)
        assert observation_point_names(item) == expected.names
        np.testing.assert_array_equal(result.coordinate_values, expected.xyz)
        np.testing.assert_array_equal(result.confidence_scores, expected.visibility)


def test_recording_assembly_batches_frames_and_preserves_sparse_reordered_identities():
    buffer = ObservationBuffer()
    for frame in range(513):
        item = observation(frame, names=("first", "second") if frame % 2 else ("second", "first"),
                           confidence=(np.nan, 0.) if frame == 256 else (0.8, 0.5))
        buffer.add_observation(item)
    with patch.object(Observation, "to_keypoints", side_effect=AssertionError("Rebuilt Keypoints")):
        names = buffer.keypoint_names
        result = buffer.to_keypoints_array(names=names)
    assert names == ("body.second", "body.first")
    np.testing.assert_array_equal(result[0], result[1, ::-1])
    assert np.isnan(result[256]).all()
    np.testing.assert_array_equal(result[0], result[512])


def test_prepared_indices_are_reused_immutable_and_reject_unknown_identities():
    first = point_selection(("b", "a"), ("a", "b"))
    assert point_selection(("b", "a"), ("a", "b")) is first
    with pytest.raises(ValueError):
        first[1].flags.writeable = True
    with pytest.raises(ValueError, match="missing from"):
        point_selection(("a", "b"), ("a",))
    with pytest.raises(ValueError, match="Duplicate"):
        point_selection(("a", "a"), ("a",))


def test_matching_ranks_same_cross_camera_evidence_with_array_reduction():
    frames = [{"a": observation(), "b": observation(confidence=(0.6, 0.9))},
              {"a": observation(1, confidence=(0.1, 0.8)), "b": observation(1, confidence=(0.1, 0.8))}]
    with patch.object(Observation, "to_keypoints", side_effect=AssertionError("Rebuilt Keypoints")):
        assert select_matching_point_names(frames=frames, minimum_visibility=0.4) == ("body.first", "body.second")


def test_empty_and_duplicate_stage_names_are_not_silently_repaired():
    empty = observation_arrays(Observation(frame_number=0, image_size=(120, 160)))
    assert empty.coordinate_values.shape == (0, 3)
    item = observation()
    item.stages["duplicate"] = item.stages["body"]
    with pytest.raises(ValueError, match="Duplicate"):
        observation_arrays(item)
