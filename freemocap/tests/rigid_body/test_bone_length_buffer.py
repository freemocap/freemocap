"""Unit tests for the streaming best-K bone-length buffer.

The buffer keeps the best-K bone-length measurements seen so far, ranked by
reprojection error with an age decay, and reports their median. It is the
realtime analogue of the posthoc pipeline's per-bone median over all frames.
"""
import pytest

from freemocap.core.tasks.mocap.rigid_body.online_segment_lengths import BoneLengthBuffer


def test_estimate_is_seed_when_empty():
    buf = BoneLengthBuffer(capacity=4, decay_tau_s=10.0, seed_length=100.0)
    assert buf.estimate == 100.0
    assert len(buf) == 0


def test_estimate_is_median_of_accepted_samples():
    buf = BoneLengthBuffer(capacity=8, decay_tau_s=1e12, seed_length=100.0)
    for i, length in enumerate([90.0, 110.0, 100.0]):
        assert buf.offer(length=length, error=1.0, t=float(i)) is True
    assert buf.estimate == 100.0  # median of {90, 100, 110}


def test_reproj_gate_drops_high_error_samples():
    buf = BoneLengthBuffer(capacity=8, decay_tau_s=1e12, seed_length=100.0, max_error=5.0)
    assert buf.offer(length=400.0, error=50.0, t=0.0) is False  # error above gate
    assert len(buf) == 0
    assert buf.estimate == 100.0  # untouched -> still the seed


def test_keeps_best_k_by_error_when_over_capacity():
    # capacity 2, effectively no decay: the worst-error sample must not survive.
    buf = BoneLengthBuffer(capacity=2, decay_tau_s=1e12, seed_length=100.0)
    buf.offer(length=200.0, error=1.0, t=0.0)
    buf.offer(length=201.0, error=2.0, t=1.0)
    buf.offer(length=999.0, error=9.0, t=2.0)  # worst error -> evicted
    assert len(buf) == 2
    assert buf.estimate == 200.5  # median of {200, 201}


def test_decay_lets_fresh_sample_replace_stale_better_one():
    # With a short decay, a stale low-error sample is evicted for a fresh,
    # higher-error one (age inflates the stale sample's effective error).
    buf = BoneLengthBuffer(capacity=1, decay_tau_s=1.0, seed_length=100.0)
    buf.offer(length=200.0, error=0.1, t=0.0)
    assert buf.estimate == 200.0
    buf.offer(length=250.0, error=1.0, t=100.0)  # much later
    assert buf.estimate == 250.0


def test_no_decay_keeps_lower_error_sample():
    # With negligible decay, the lower-error sample wins regardless of age.
    buf = BoneLengthBuffer(capacity=1, decay_tau_s=1e12, seed_length=100.0)
    buf.offer(length=200.0, error=0.1, t=0.0)
    assert buf.offer(length=250.0, error=1.0, t=100.0) is False  # higher error -> rejected
    assert buf.estimate == 200.0


def test_plausibility_gate_drops_wild_lengths():
    buf = BoneLengthBuffer(capacity=8, decay_tau_s=1e12, seed_length=100.0, plausibility_tol=0.2)
    for i in range(5):
        buf.offer(length=300.0, error=1.0, t=float(i))  # establish a 300 mm median
    assert buf.offer(length=600.0, error=1.0, t=5.0) is False  # 2x median -> implausible
    assert buf.estimate == 300.0
