"""Unit tests for the multi-bone online length manager."""
import numpy as np
import pytest

from freemocap.core.tasks.mocap.rigid_body.online_segment_lengths import OnlineBoneLengths


def _make(**overrides) -> OnlineBoneLengths:
    kwargs = dict(
        bone_seeds={"a->b": 100.0, "b->c": 80.0},
        capacity=8,
        decay_tau_s=1e12,
        min_samples=1,
        fit_ratio=1.0,
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


def test_trust_region_rejects_out_of_spec_measurement():
    online = _make(fit_ratio=0.2)  # region for seed 100: [80, 120]
    positions = {"a": np.zeros(3), "b": np.array([0.0, 150.0, 0.0])}
    online.update(positions, errors={"a": 1.0, "b": 1.0}, t=0.0)
    assert online.lengths["a->b"] == 100.0  # 150 is out of region -> seed stands


def test_agreement_required_before_leaving_seed():
    online = _make(min_samples=5, fit_ratio=0.5)  # region for seed 100: [50, 150]
    positions = {"a": np.zeros(3), "b": np.array([0.0, 130.0, 0.0])}
    for i in range(4):
        online.update(positions, errors={"a": 1.0, "b": 1.0}, t=float(i))
    assert online.lengths["a->b"] == 100.0  # 4 < min_samples
    assert online.agreed_medians()["a->b"] is None
    online.update(positions, errors={"a": 1.0, "b": 1.0}, t=4.0)
    assert online.lengths["a->b"] == pytest.approx(130.0)
    assert online.agreed_medians()["a->b"] == pytest.approx(130.0)


def test_reseed_reanchors_bones():
    online = _make()
    online.reseed({"a->b": 300.0})
    assert online.lengths["a->b"] == 300.0
    assert online.seeds["a->b"] == 300.0
    assert online.lengths["b->c"] == 80.0  # untouched


def test_reseed_unknown_bone_raises():
    online = _make()
    with pytest.raises(KeyError):
        online.reseed({"x->y": 100.0})


def test_reset_restores_seeds():
    online = _make()
    online.update(
        {"a": np.array([0.0, 0.0, 0.0]), "b": np.array([0.0, 150.0, 0.0])},
        errors={"a": 1.0, "b": 1.0},
        t=0.0,
    )
    assert online.lengths["a->b"] == 150.0  # learned a real length, not the seed

    online.reset()

    assert online.lengths == {"a->b": 100.0, "b->c": 80.0}  # every buffer back to its seed
