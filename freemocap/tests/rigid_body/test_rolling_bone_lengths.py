"""Unit tests for the rolling-window median bone-length estimator.

Each bone reports the median of its measured lengths over the last ``window_s``
seconds — the streaming analogue of the posthoc per-bone median — and falls back
to its anthropometric seed whenever the window is empty. No trust region, no
agreement gating, no error weighting: a plain rolling median.
"""
import numpy as np

from freemocap.core.tasks.mocap.rigid_body.online_segment_lengths import RollingBoneLengths


def _make(**overrides) -> RollingBoneLengths:
    kwargs = dict(
        bone_seeds={"a->b": 100.0, "b->c": 80.0},
        window_s=10.0,
    )
    kwargs.update(overrides)
    return RollingBoneLengths(**kwargs)


def _ab(length: float) -> dict[str, np.ndarray]:
    """Positions that make |b - a| == length (b->c left unmeasured)."""
    return {"a": np.array([0.0, 0.0, 0.0]), "b": np.array([0.0, length, 0.0])}


def test_lengths_are_seeds_before_any_update():
    rolling = _make()
    assert rolling.lengths == {"a->b": 100.0, "b->c": 80.0}


def test_single_measurement_used_immediately():
    # Pure median: one sample is its own median — no min-samples bootstrap.
    rolling = _make()
    rolling.update(_ab(150.0), t=0.0)
    assert rolling.lengths["a->b"] == 150.0
    assert rolling.lengths["b->c"] == 80.0  # never measured -> seed


def test_lengths_is_median_of_window():
    rolling = _make()
    for i, length in enumerate((140.0, 150.0, 160.0)):
        rolling.update(_ab(length), t=float(i))
    assert rolling.lengths["a->b"] == 150.0  # median of 3


def test_median_of_even_count_is_mean_of_middle_two():
    rolling = _make()
    for i, length in enumerate((140.0, 160.0)):
        rolling.update(_ab(length), t=float(i))
    assert rolling.lengths["a->b"] == 150.0  # numpy median of 2 -> mean


def test_bone_with_missing_endpoint_is_not_measured():
    rolling = _make()
    rolling.update({"a": np.array([0.0, 0.0, 0.0])}, t=0.0)  # b, c absent
    assert rolling.lengths["a->b"] == 100.0
    assert rolling.lengths["b->c"] == 80.0


def test_measurements_older_than_window_are_evicted():
    rolling = _make(window_s=10.0)
    rolling.update(_ab(100.0), t=0.0)
    rolling.update(_ab(200.0), t=5.0)
    assert rolling.lengths["a->b"] == 150.0  # median {100, 200}
    rolling.update(_ab(300.0), t=11.0)  # t=0 sample is now >10s old -> evicted
    assert rolling.lengths["a->b"] == 250.0  # median {200, 300}


def test_unseen_bone_falls_back_to_seed_after_window():
    # A bone that drops out of view longer than the window loses all samples and
    # returns to its seed — eviction is by wall-clock, not only on measurement.
    rolling = _make(window_s=10.0)
    rolling.update(_ab(150.0), t=0.0)
    assert rolling.lengths["a->b"] == 150.0
    rolling.update({"b": np.array([0.0, 0.0, 0.0]), "c": np.array([0.0, 90.0, 0.0])}, t=100.0)
    assert rolling.lengths["a->b"] == 100.0  # a->b window emptied -> seed
    assert rolling.lengths["b->c"] == 90.0   # b->c freshly measured


def test_reset_restores_seeds():
    rolling = _make()
    rolling.update(_ab(150.0), t=0.0)
    assert rolling.lengths["a->b"] == 150.0
    rolling.reset()
    assert rolling.lengths == {"a->b": 100.0, "b->c": 80.0}
