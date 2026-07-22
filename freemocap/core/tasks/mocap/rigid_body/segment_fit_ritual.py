"""Segment-fit calibration ritual for the realtime skeleton fitter.

State machine that turns "reset the skeleton fit" from an instant next-frame
re-fit into a gated capture: a countdown (so the subject can get into view and
hold still), a quality-gated capture window (only consecutive good frames
count), then a freeze that re-anchors each bone's trust region on the captured
length (see ``OnlineBoneLengths.reseed``). Bones that never reach agreement —
hands out of frame, a limb never visible — keep their seeds and stay live.

    IDLE        — normal live fitting (the hardened buffers — trust region,
                  agreement gating, error ranking — do the work).
    COUNTDOWN   — armed; buffers cleared; no updates until the deadline passes.
    CAPTURING   — updates only on quality-gated frames; a bad frame resets the
                  consecutive-good streak.
    FITTED      — captured bones are re-anchored; updates continue, so lengths
                  drift slowly inside the re-anchored trust region.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from freemocap.core.tasks.mocap.rigid_body.online_segment_lengths import OnlineBoneLengths


class FitRitualState(StrEnum):
    IDLE = "idle"
    COUNTDOWN = "countdown"
    CAPTURING = "capturing"
    FITTED = "fitted"


@dataclass(slots=True, frozen=True)
class FitStateSnapshot:
    """Point-in-time view of the ritual, for publication to the frontend."""

    state: str
    countdown_remaining_s: float
    capture_good_streak: int
    capture_required_good_frames: int
    visible_fraction: float
    mean_error_px: float | None
    n_fitted_body_bones: int
    median_seed_deviation: float | None


class SegmentFitRitual:
    """Countdown → gated capture → freeze state machine over the three length managers."""

    def __init__(
        self,
        *,
        body_lengths: OnlineBoneLengths,
        rhand_lengths: OnlineBoneLengths,
        lhand_lengths: OnlineBoneLengths,
        countdown_s: float,
        capture_min_visible_fraction: float,
        capture_max_mean_error_px: float,
        capture_consecutive_good_frames: int,
    ) -> None:
        self._lengths = {
            "body": body_lengths,
            "rhand": rhand_lengths,
            "lhand": lhand_lengths,
        }
        self._body_endpoints = body_lengths.endpoints
        self._countdown_s = float(countdown_s)
        self._min_visible = float(capture_min_visible_fraction)
        self._max_mean_error = float(capture_max_mean_error_px)
        # The freeze can only capture bones whose buffers reached agreement,
        # which needs min_samples consecutive samples — so the required streak
        # can never be shorter than the largest min_samples. Enforcing it here
        # keeps the invariant true regardless of config.
        self._required_good_frames = max(
            int(capture_consecutive_good_frames),
            max(m.min_samples for m in (body_lengths, rhand_lengths, lhand_lengths)),
        )

        self._state = FitRitualState.IDLE
        self._refit_pending = False
        self._deadline_t = 0.0
        self._good_streak = 0
        self._last_t = 0.0
        self._n_fitted_body_bones = 0
        self._median_seed_deviation: float | None = None
        self._last_visible_fraction = 0.0
        self._last_mean_error_px: float | None = None

    def request_refit(self) -> None:
        """Arm the ritual: the next frame starts the countdown."""
        self._refit_pending = True

    @property
    def state(self) -> FitRitualState:
        return self._state

    def on_frame(
        self,
        *,
        measured_body: dict[str, np.ndarray],
        measured_rhand: dict[str, np.ndarray],
        measured_lhand: dict[str, np.ndarray],
        errors_body: dict[str, float] | None,
        errors_rhand: dict[str, float] | None,
        errors_lhand: dict[str, float] | None,
        t: float,
    ) -> None:
        """Advance the state machine by one frame and apply its update policy."""
        self._last_t = t
        self._last_visible_fraction = self._visible_fraction(measured_body)
        self._last_mean_error_px = self._mean_error(measured_body, errors_body)

        if self._refit_pending:
            self._refit_pending = False
            for lengths in self._lengths.values():
                lengths.reset()
            self._state = FitRitualState.COUNTDOWN
            self._deadline_t = t + self._countdown_s
            self._good_streak = 0
            self._n_fitted_body_bones = 0
            self._median_seed_deviation = None

        if self._state is FitRitualState.COUNTDOWN:
            if t >= self._deadline_t:
                self._state = FitRitualState.CAPTURING
            return

        if self._state is FitRitualState.CAPTURING:
            good = (
                self._last_visible_fraction >= self._min_visible
                and (
                    self._last_mean_error_px is None
                    or self._last_mean_error_px <= self._max_mean_error
                )
            )
            if not good:
                self._good_streak = 0
                return
            self._update_all(
                measured_body, measured_rhand, measured_lhand,
                errors_body, errors_rhand, errors_lhand, t,
            )
            self._good_streak += 1
            if self._good_streak >= self._required_good_frames:
                self._freeze()
                self._state = FitRitualState.FITTED
            return

        # IDLE and FITTED both update every frame; FITTED bones are re-anchored,
        # so their updates drift only inside the captured trust region.
        self._update_all(
            measured_body, measured_rhand, measured_lhand,
            errors_body, errors_rhand, errors_lhand, t,
        )

    def _visible_fraction(self, measured_body: dict[str, np.ndarray]) -> float:
        expected = {name for endpoints in self._body_endpoints.values() for name in endpoints}
        present = sum(1 for name in expected if name in measured_body)
        return present / len(expected)

    @staticmethod
    def _mean_error(
        measured_body: dict[str, np.ndarray],
        errors_body: dict[str, float] | None,
    ) -> float | None:
        if errors_body is None:
            return None
        vals = [errors_body[name] for name in measured_body if name in errors_body]
        if not vals:
            return None
        return float(np.mean(vals))

    def _update_all(
        self,
        measured_body: dict[str, np.ndarray],
        measured_rhand: dict[str, np.ndarray],
        measured_lhand: dict[str, np.ndarray],
        errors_body: dict[str, float] | None,
        errors_rhand: dict[str, float] | None,
        errors_lhand: dict[str, float] | None,
        t: float,
    ) -> None:
        self._lengths["body"].update(measured_body, t=t, errors=errors_body)
        self._lengths["rhand"].update(measured_rhand, t=t, errors=errors_rhand)
        self._lengths["lhand"].update(measured_lhand, t=t, errors=errors_lhand)

    def _freeze(self) -> None:
        """Re-anchor every bone that reached agreement on its captured length."""
        deviations: list[float] = []
        for tree_name, lengths in self._lengths.items():
            medians = lengths.agreed_medians()
            seeds = lengths.seeds
            captured = {bone: m for bone, m in medians.items() if m is not None}
            if not captured:
                continue
            if tree_name == "body":
                self._n_fitted_body_bones = len(captured)
                deviations = [
                    abs(captured[bone] - seeds[bone]) / seeds[bone]
                    for bone in captured
                ]
            lengths.reseed(captured)
        if deviations:
            self._median_seed_deviation = float(np.median(deviations))

    def snapshot(self) -> FitStateSnapshot:
        countdown_remaining = (
            max(0.0, self._deadline_t - self._last_t)
            if self._state is FitRitualState.COUNTDOWN
            else 0.0
        )
        return FitStateSnapshot(
            state=str(self._state),
            countdown_remaining_s=countdown_remaining,
            capture_good_streak=self._good_streak,
            capture_required_good_frames=self._required_good_frames,
            visible_fraction=self._last_visible_fraction,
            mean_error_px=self._last_mean_error_px,
            n_fitted_body_bones=self._n_fitted_body_bones,
            median_seed_deviation=self._median_seed_deviation,
        )
