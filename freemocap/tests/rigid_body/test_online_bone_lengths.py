"""Unit tests for the multi-bone online length manager."""
import numpy as np

from freemocap.core.tasks.mocap.rigid_body.online_segment_lengths import OnlineBoneLengths


def _make(**overrides) -> OnlineBoneLengths:
    kwargs = dict(
        bone_seeds={"a->b": 100.0, "b->c": 80.0},
        capacity=8,
        decay_tau_s=1e12,
    )
    kwargs.update(overrides)
    return OnlineBoneLengths(**kwargs)


def test_lengths_are_seeds_before_any_update():
    online = _make()
    assert online.lengths == {"a->b": 100.0, "b->c": 80.0}


def test_update_measures_observed_bones():
    online = _make()
    positions = {
        "a": np.array([0.0, 0.0, 0.0]),
        "b": np.array([0.0, 150.0, 0.0]),
        "c": np.array([0.0, 150.0, 90.0]),
    }
    online.update(positions, errors={"a": 1.0, "b": 1.0, "c": 1.0}, t=0.0)
    assert online.lengths["a->b"] == 150.0  # |b - a|
    assert online.lengths["b->c"] == 90.0   # |c - b|


def test_bone_with_missing_endpoint_keeps_seed():
    online = _make()
    online.update({"a": np.array([0.0, 0.0, 0.0])}, errors={"a": 1.0}, t=0.0)  # b, c missing
    assert online.lengths["a->b"] == 100.0  # untouched seed
    assert online.lengths["b->c"] == 80.0


def test_bone_error_is_worst_endpoint_and_gates():
    # b has a high reprojection error -> both bones touching b are gated out.
    online = _make(max_error=5.0)
    positions = {
        "a": np.array([0.0, 0.0, 0.0]),
        "b": np.array([0.0, 150.0, 0.0]),
        "c": np.array([0.0, 150.0, 90.0]),
    }
    online.update(positions, errors={"a": 1.0, "b": 50.0, "c": 1.0}, t=0.0)
    assert online.lengths["a->b"] == 100.0  # gated (b bad) -> seed
    assert online.lengths["b->c"] == 80.0   # gated (b bad) -> seed


def test_update_without_errors_still_measures():
    online = _make(max_error=5.0)
    positions = {"a": np.array([0.0, 0.0, 0.0]), "b": np.array([0.0, 150.0, 0.0])}
    online.update(positions, t=0.0)  # no errors -> treated as confident
    assert online.lengths["a->b"] == 150.0
