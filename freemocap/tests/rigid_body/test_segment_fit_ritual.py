"""Unit tests for the segment-fit calibration ritual state machine."""
import numpy as np
import pytest

from freemocap.core.tasks.mocap.rigid_body.online_segment_lengths import OnlineBoneLengths
from freemocap.core.tasks.mocap.rigid_body.segment_fit_ritual import (
    FitRitualState,
    SegmentFitRitual,
)

# Measured bone lengths in the synthetic frames: 440 / 330 (seeds 400 / 300,
# both inside the fit_ratio=0.5 trust region).
HIPS = np.array([0.0, 0.0, 0.0])
SPINE = np.array([0.0, 440.0, 0.0])
CHEST = np.array([0.0, 770.0, 0.0])
NECK = np.array([0.0, 580.0, 0.0])  # |neck - spine| = 140, region [50, 150]

GOOD_FRAME = {"hips": HIPS, "spine": SPINE, "chest": CHEST}


def _lengths(seeds: dict[str, float] | None = None, **overrides) -> OnlineBoneLengths:
    kwargs = dict(
        bone_seeds=seeds or {"hips->spine": 400.0, "spine->chest": 300.0},
        capacity=16,
        decay_tau_s=1e12,
        fit_ratio=0.5,
        min_samples=3,
        agreement_tol=0.05,
    )
    kwargs.update(overrides)
    return OnlineBoneLengths(**kwargs)


def _ritual(body: OnlineBoneLengths, **overrides) -> SegmentFitRitual:
    kwargs = dict(
        body_lengths=body,
        rhand_lengths=_lengths({"ra->rb": 10.0}),
        lhand_lengths=_lengths({"la->lb": 10.0}),
        countdown_s=1.0,
        capture_min_visible_fraction=0.5,
        capture_max_mean_error_px=5.0,
        capture_consecutive_good_frames=3,
    )
    kwargs.update(overrides)
    return SegmentFitRitual(**kwargs)


def _frame(ritual: SegmentFitRitual, t: float, body_frame=None, errors_body=None) -> None:
    ritual.on_frame(
        measured_body=GOOD_FRAME if body_frame is None else body_frame,
        measured_rhand={},
        measured_lhand={},
        errors_body=errors_body,
        errors_rhand=None,
        errors_lhand=None,
        t=t,
    )


def test_idle_updates_normally():
    body = _lengths()
    ritual = _ritual(body)
    for i in range(3):
        _frame(ritual, t=float(i))
    assert ritual.state == FitRitualState.IDLE
    assert body.lengths["hips->spine"] == pytest.approx(440.0)
    assert body.lengths["spine->chest"] == pytest.approx(330.0)


def test_refit_countdown_blocks_updates_and_restores_seeds():
    body = _lengths()
    ritual = _ritual(body)
    for i in range(3):
        _frame(ritual, t=float(i))
    assert body.lengths["hips->spine"] == pytest.approx(440.0)  # learned

    ritual.request_refit()
    _frame(ritual, t=10.0)  # countdown begins; buffers cleared

    assert ritual.state == FitRitualState.COUNTDOWN
    assert body.lengths["hips->spine"] == 400.0  # back to the seed

    _frame(ritual, t=10.5)  # deadline is 11.0 — still counting down
    assert body.lengths["hips->spine"] == 400.0  # no updates during countdown

    snap = ritual.snapshot()
    assert snap.state == "countdown"
    assert snap.countdown_remaining_s == pytest.approx(0.5)
    assert snap.visible_fraction == 1.0


def test_capture_freezes_after_consecutive_good_frames():
    body = _lengths()
    ritual = _ritual(body)
    ritual.request_refit()
    _frame(ritual, t=10.0)  # armed
    _frame(ritual, t=11.0)  # deadline reached -> CAPTURING

    _frame(ritual, t=11.1)  # good frame 1
    _frame(ritual, t=11.2)  # good frame 2
    assert ritual.state == FitRitualState.CAPTURING
    assert body.lengths["hips->spine"] == 400.0  # not frozen yet

    _frame(ritual, t=11.3)  # good frame 3 -> freeze
    assert ritual.state == FitRitualState.FITTED
    assert body.lengths["hips->spine"] == pytest.approx(440.0)  # captured re-anchor
    assert body.lengths["spine->chest"] == pytest.approx(330.0)

    snap = ritual.snapshot()
    assert snap.n_fitted_body_bones == 2
    # Both captured lengths deviate 10% from their seeds.
    assert snap.median_seed_deviation == pytest.approx(0.1)


def test_bad_frame_resets_good_streak():
    body = _lengths()
    ritual = _ritual(body)
    ritual.request_refit()
    _frame(ritual, t=10.0)
    _frame(ritual, t=11.0)  # capturing

    _frame(ritual, t=11.1)  # streak 1
    _frame(ritual, t=11.2)  # streak 2
    _frame(ritual, t=11.3, body_frame={"hips": HIPS})  # low visibility -> streak 0
    _frame(ritual, t=11.4, errors_body={"hips": 50.0, "spine": 50.0, "chest": 50.0})  # high error -> 0
    assert ritual.state == FitRitualState.CAPTURING
    assert ritual.snapshot().capture_good_streak == 0

    _frame(ritual, t=11.5)
    _frame(ritual, t=11.6)
    assert ritual.state == FitRitualState.CAPTURING
    _frame(ritual, t=11.7)
    assert ritual.state == FitRitualState.FITTED


def test_unfitted_bones_keep_seeds_and_stay_live():
    body = _lengths({"hips->spine": 400.0, "spine->chest": 300.0, "spine->neck": 100.0})
    ritual = _ritual(body)
    ritual.request_refit()
    _frame(ritual, t=10.0)
    _frame(ritual, t=11.0)
    for i in range(3):
        _frame(ritual, t=11.1 + i * 0.1)  # neck never visible -> never agrees

    assert ritual.state == FitRitualState.FITTED
    assert body.lengths["spine->neck"] == 100.0  # seed kept (not captured)
    assert ritual.snapshot().n_fitted_body_bones == 2

    # FITTED keeps updating: the never-fitted bone can still learn, bounded
    # by its own (still anthropometric) trust region.
    full = dict(GOOD_FRAME, neck=NECK)
    for i in range(3):
        _frame(ritual, t=12.0 + i * 0.1, body_frame=full)
    assert body.lengths["spine->neck"] == pytest.approx(140.0)


def test_fitted_drift_is_bounded_by_captured_anchor():
    body = _lengths()
    ritual = _ritual(body)
    ritual.request_refit()
    _frame(ritual, t=10.0)
    _frame(ritual, t=11.0)
    for i in range(3):
        _frame(ritual, t=11.1 + i * 0.1)
    assert ritual.state == FitRitualState.FITTED

    # A wild measurement after the freeze is rejected by the re-anchored
    # trust region (440 x (1 +/- 0.5) = [220, 660]).
    wild = dict(GOOD_FRAME, spine=np.array([0.0, 900.0, 0.0]))
    _frame(ritual, t=12.0, body_frame=wild)
    assert body.lengths["hips->spine"] == pytest.approx(440.0)
