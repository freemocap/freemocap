"""Unit tests for the realtime One Euro keypoint filter's prediction provenance."""
import numpy as np

from freemocap.core.pipeline.realtime.realtime_keypoint_filter import RealtimeKeypointFilter


def test_observed_points_are_not_predicted():
    f = RealtimeKeypointFilter(dims=3)
    out = f.filter(t=0.0, raw_keypoints={"nose": np.array([1.0, 2.0, 3.0])})
    np.testing.assert_allclose(out.positions["nose"], [1.0, 2.0, 3.0])
    assert out.predicted_names == frozenset()


def test_missing_point_is_gap_filled_and_flagged():
    f = RealtimeKeypointFilter(dims=3)
    f.filter(t=0.0, raw_keypoints={"nose": np.array([1.0, 2.0, 3.0])})
    out = f.filter(t=0.1, raw_keypoints={})
    assert "nose" in out.positions  # gap-filled so display doesn't blink
    assert out.predicted_names == frozenset({"nose"})


def test_prediction_stops_after_max_frames():
    f = RealtimeKeypointFilter(dims=3, max_prediction_frames=2)
    f.filter(t=0.0, raw_keypoints={"nose": np.zeros(3)})
    f.filter(t=0.1, raw_keypoints={})
    f.filter(t=0.2, raw_keypoints={})
    out = f.filter(t=0.3, raw_keypoints={})
    assert "nose" not in out.positions
    assert out.predicted_names == frozenset()


def test_returning_point_is_real_again():
    f = RealtimeKeypointFilter(dims=3)
    f.filter(t=0.0, raw_keypoints={"nose": np.zeros(3)})
    f.filter(t=0.1, raw_keypoints={})
    out = f.filter(t=0.2, raw_keypoints={"nose": np.ones(3)})
    assert out.predicted_names == frozenset()


def test_reset_clears_state():
    f = RealtimeKeypointFilter(dims=3)
    f.filter(t=0.0, raw_keypoints={"nose": np.zeros(3)})
    f.reset()
    out = f.filter(t=0.1, raw_keypoints={})
    assert out.positions == {}
    assert out.predicted_names == frozenset()
