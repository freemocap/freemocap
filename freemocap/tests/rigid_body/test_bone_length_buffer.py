"""Unit tests for the streaming best-K bone-length buffer.

The buffer keeps the best-K bone-length measurements seen so far, ranked by
reprojection error with an age decay, and reports their median once enough
samples agree — always inside a trust region anchored to the seed. It is the
realtime analogue of the posthoc pipeline's per-bone median over all frames.
"""
import pytest

from freemocap.core.tasks.mocap.rigid_body.online_segment_lengths import BoneLengthBuffer


def _buf(**overrides) -> BoneLengthBuffer:
    kwargs = dict(capacity=8, decay_tau_s=1e12, seed_length=100.0)
    kwargs.update(overrides)
    return BoneLengthBuffer(**kwargs)


def test_estimate_is_seed_when_empty():
    buf = _buf()
    assert buf.estimate == 100.0
    assert len(buf) == 0


def test_single_offer_does_not_replace_seed():
    # Bootstrap protection: min_samples=5 by default — one frame teaches nothing.
    buf = _buf()
    assert buf.offer(length=110.0, error=1.0, t=0.0) is True
    assert buf.estimate == 100.0


def test_agreeing_samples_replace_seed_with_median():
    buf = _buf()
    for i in range(5):
        assert buf.offer(length=110.0 + i * 0.1, error=1.0, t=float(i)) is True
    assert buf.estimate == pytest.approx(110.2)


def test_bimodal_samples_never_replace_seed():
    # Alternating 90 / 110: relative MAD is 10% > agreement_tol (5%) — no consensus.
    buf = _buf()
    for i in range(10):
        buf.offer(length=90.0 if i % 2 == 0 else 110.0, error=1.0, t=float(i))
    assert buf.estimate == 100.0


def test_trust_region_rejects_out_of_spec_lengths():
    # seed 100, fit_ratio 0.2 -> [80, 120].
    buf = _buf(fit_ratio=0.2)
    assert buf.offer(length=79.9, error=1.0, t=0.0) is False
    assert buf.offer(length=120.1, error=1.0, t=1.0) is False
    assert buf.offer(length=80.0, error=1.0, t=2.0) is True
    assert buf.offer(length=120.0, error=1.0, t=3.0) is True


def test_trust_region_floor_is_25_percent_of_seed():
    # ratio 1.0 would allow [0, 200] — the floor clamps the lower bound to 25.
    buf = _buf(fit_ratio=1.0)
    assert buf.offer(length=24.9, error=1.0, t=0.0) is False
    assert buf.offer(length=25.0, error=1.0, t=1.0) is True
    assert buf.offer(length=200.0, error=1.0, t=2.0) is True
    assert buf.offer(length=200.1, error=1.0, t=3.0) is False


def test_garbage_stream_can_never_establish_a_new_anchor():
    # A sustained stream of out-of-region garbage is rejected forever, so the
    # estimate can never get stuck on it — and good data is still accepted after.
    buf = _buf(fit_ratio=0.2)
    for i in range(20):
        assert buf.offer(length=300.0, error=0.0, t=float(i)) is False
    assert buf.estimate == 100.0
    for i in range(5):
        assert buf.offer(length=110.0, error=1.0, t=100.0 + i) is True
    assert buf.estimate == pytest.approx(110.0)


def test_reproj_gate_drops_high_error_samples():
    buf = _buf(max_error=5.0)
    assert buf.offer(length=110.0, error=50.0, t=0.0) is False
    assert len(buf) == 0
    assert buf.estimate == 100.0


def test_keeps_best_k_by_error_when_over_capacity():
    # capacity 2, effectively no decay: the worst-error sample must not survive.
    buf = _buf(capacity=2, min_samples=1)
    buf.offer(length=110.0, error=1.0, t=0.0)
    buf.offer(length=111.0, error=2.0, t=1.0)
    buf.offer(length=112.0, error=9.0, t=2.0)  # worst error -> evicted
    assert len(buf) == 2
    assert buf.estimate == 110.5  # median of {110, 111}


def test_decay_lets_fresh_sample_replace_stale_better_one():
    # With a short decay, a stale low-error sample is evicted for a fresh,
    # higher-error one (age inflates the stale sample's effective error).
    buf = _buf(capacity=1, decay_tau_s=1.0, min_samples=1)
    buf.offer(length=110.0, error=0.1, t=0.0)
    assert buf.estimate == 110.0
    buf.offer(length=115.0, error=1.0, t=100.0)  # much later
    assert buf.estimate == 115.0


def test_no_decay_keeps_lower_error_sample():
    # With negligible decay, the lower-error sample wins regardless of age.
    buf = _buf(capacity=1, min_samples=1)
    buf.offer(length=110.0, error=0.1, t=0.0)
    assert buf.offer(length=115.0, error=1.0, t=100.0) is False  # higher error -> rejected
    assert buf.estimate == 110.0


def test_reseed_reanchors_and_clears():
    buf = _buf(fit_ratio=0.2)
    for i in range(5):
        buf.offer(length=110.0, error=1.0, t=float(i))
    assert buf.estimate == pytest.approx(110.0)

    buf.reseed(300.0)

    assert buf.estimate == 300.0
    assert len(buf) == 0
    # The trust region re-centered: 110 is now out of spec, 330 is in.
    assert buf.offer(length=110.0, error=1.0, t=10.0) is False
    for i in range(5):
        assert buf.offer(length=330.0, error=1.0, t=20.0 + i) is True
    assert buf.estimate == pytest.approx(330.0)


def test_reseed_rejects_invalid_length():
    buf = _buf()
    with pytest.raises(ValueError):
        buf.reseed(0.0)
    with pytest.raises(ValueError):
        buf.reseed(float("nan"))
