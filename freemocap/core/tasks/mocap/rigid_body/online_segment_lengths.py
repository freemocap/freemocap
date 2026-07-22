"""Streaming bone-length estimation for realtime rigid-body skeleton correction.

Each bone keeps a bounded "best-K" buffer of length measurements ranked by
reprojection error with an age decay, and reports their **median** — the realtime
analogue of the posthoc pipeline's per-bone median over the whole recording
(skellyforge ``enforce_rigid_bones.calculate_bone_lengths_and_statistics``).

Two guards keep the estimate honest:

* **Trust region** — a measurement only enters the buffer if it lands within
  ``seed_length × (1 ± fit_ratio)`` (lower bound floored at 25% of the seed),
  and the reported estimate is clamped to the same band. The anchor is the
  seed — the anthropometric prior, or a captured calibration via ``reseed`` —
  never the buffer's own contents, so no stream of garbage can drag the
  estimate out of spec or redefine what "plausible" means.
* **Bootstrap agreement** — the buffer only replaces its seed once
  ``min_samples`` retained measurements agree with each other (relative MAD
  within ``agreement_tol``). One frame — or a flickering stream — teaches
  nothing.

Why best-K-by-error instead of a recency window: a bone length is (assumed)
stationary, so the best estimate comes from the highest-quality observations
*ever* seen, not merely the most recent ones. The age decay (``decay_tau_s``)
keeps the estimate from getting permanently stuck on stale data — an old
sample's *effective* error grows with age, so it eventually loses its buffer
slot to fresher, decent measurements.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


@dataclass(slots=True)
class _Sample:
    length: float
    error: float
    t: float


def _clamp(x: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, x))


@dataclass
class BoneLengthBuffer:
    """Best-K-by-reprojection-error buffer of one bone's length measurements.

    Parameters
    ----------
    capacity : int
        Max measurements retained (K). When exceeded, the worst (by age-decayed
        reprojection error) is evicted.
    decay_tau_s : float
        Age-decay time constant (seconds). A stored sample's effective error is
        ``error * exp(age / decay_tau_s)``, so stale samples lose their slot.
    seed_length : float
        Anthropometric prior (mm) returned until the buffer reaches agreement,
        and the anchor of the trust region. Replaced by ``reseed``.
    fit_ratio : float
        Trust-region half-width as a fraction of the seed: measurements outside
        ``seed × (1 ± fit_ratio)`` (lower bound floored at ``seed × 0.25``) are
        rejected outright.
    min_samples : int
        Minimum retained measurements before the buffer may leave its seed.
    agreement_tol : float
        Max relative MAD (median absolute deviation / median) across retained
        samples for the buffer to count as agreeing.
    max_error : float | None
        Reprojection-error gate: measurements above this are dropped outright.
    """

    capacity: int
    decay_tau_s: float
    seed_length: float
    fit_ratio: float = 0.2
    min_samples: int = 5
    agreement_tol: float = 0.05
    max_error: float | None = None

    _samples: list[_Sample] = field(default_factory=list, init=False, repr=False)

    @property
    def trust_region(self) -> tuple[float, float]:
        """(lower, upper) acceptable length band (mm), anchored to the seed."""
        lower = max(self.seed_length * (1.0 - self.fit_ratio), self.seed_length * 0.25)
        upper = self.seed_length * (1.0 + self.fit_ratio)
        return lower, upper

    def offer(self, *, length: float, error: float, t: float) -> bool:
        """Offer one measurement. Returns True if it is retained in the buffer."""
        if not math.isfinite(length) or length <= 0.0:
            return False
        if self.max_error is not None and error > self.max_error:
            return False
        lower, upper = self.trust_region
        if length < lower or length > upper:
            return False

        new_sample = _Sample(length=float(length), error=float(error), t=float(t))
        self._samples.append(new_sample)
        if len(self._samples) > self.capacity:
            evicted = self._evict_worst(now=t)
            if evicted is new_sample:
                return False
        return True

    def _evict_worst(self, *, now: float) -> _Sample:
        worst_idx = max(
            range(len(self._samples)),
            key=lambda i: self._effective_error(self._samples[i], now=now),
        )
        return self._samples.pop(worst_idx)

    def _effective_error(self, sample: _Sample, *, now: float) -> float:
        age = now - sample.t
        if age <= 0.0:
            return sample.error
        return sample.error * math.exp(age / self.decay_tau_s)

    def agreed_median(self) -> float | None:
        """Buffer consensus length (mm), or None when there is no consensus.

        Consensus requires ``min_samples`` retained measurements whose relative
        MAD is within ``agreement_tol`` — a flickering or bimodal measurement
        stream has no opinion and the seed stands.
        """
        if len(self._samples) < self.min_samples:
            return None
        lengths = np.asarray([s.length for s in self._samples], dtype=float)
        median = float(np.median(lengths))
        mad = float(np.median(np.abs(lengths - median)))
        if mad / median > self.agreement_tol:
            return None
        return median

    @property
    def estimate(self) -> float:
        """Current best length estimate (mm): the agreed median if the buffer
        has consensus, else the seed — never outside the trust region."""
        median = self.agreed_median()
        if median is None:
            return self.seed_length
        lower, upper = self.trust_region
        return _clamp(median, lower, upper)

    def reseed(self, new_seed: float) -> None:
        """Re-anchor on a captured length: replace the seed, forget measurements.

        The trust region re-centers on ``new_seed`` and the estimate falls back
        to it until fresh agreement accumulates — captured calibration with
        bounded drift.
        """
        if not math.isfinite(new_seed) or new_seed <= 0.0:
            raise ValueError(f"reseed requires a positive finite length, got {new_seed}")
        self.seed_length = float(new_seed)
        self._samples.clear()

    def __len__(self) -> int:
        return len(self._samples)

    def reset(self) -> None:
        """Forget all measurements — the estimate falls back to the seed."""
        self._samples.clear()


@dataclass
class OnlineBoneLengths:
    """One ``BoneLengthBuffer`` per bone, seeded from anthropometric ratios.

    ``update`` is called once per frame with the current canonical-named 3D
    positions of **real** (measured, not extrapolated) keypoints and
    (optionally) per-keypoint reprojection errors; ``lengths`` returns the
    current best length estimate per bone for the rigidifier.

    Parameters
    ----------
    bone_seeds : dict[str, float]
        ``"parent->child" -> seed length (mm)`` (ratio x height). Defines which
        bones are tracked and their starting estimates.
    capacity, decay_tau_s, fit_ratio, min_samples, agreement_tol, max_error
        Per-bone buffer settings (see ``BoneLengthBuffer``).
    """

    bone_seeds: dict[str, float]
    capacity: int
    decay_tau_s: float
    fit_ratio: float = 0.2
    min_samples: int = 5
    agreement_tol: float = 0.05
    max_error: float | None = None

    _buffers: dict[str, BoneLengthBuffer] = field(default_factory=dict, init=False, repr=False)
    _endpoints: dict[str, tuple[str, str]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        for bone_key, seed in self.bone_seeds.items():
            parent, child = bone_key.split("->", 1)
            self._endpoints[bone_key] = (parent, child)
            self._buffers[bone_key] = BoneLengthBuffer(
                capacity=self.capacity,
                decay_tau_s=self.decay_tau_s,
                seed_length=float(seed),
                fit_ratio=self.fit_ratio,
                min_samples=self.min_samples,
                agreement_tol=self.agreement_tol,
                max_error=self.max_error,
            )

    @property
    def endpoints(self) -> dict[str, tuple[str, str]]:
        """``"parent->child" -> (parent, child)`` for every tracked bone."""
        return dict(self._endpoints)

    def update(
        self,
        positions: dict[str, np.ndarray],
        *,
        t: float,
        errors: dict[str, float] | None = None,
    ) -> None:
        """Offer this frame's per-bone length measurements to their buffers.

        A bone is measured only when both endpoints are present. Its measurement
        error is the **worse** of the two endpoints' reprojection errors (a bone
        is only as trustworthy as its less-certain endpoint). When ``errors``
        is None, measurements are treated as fully confident (error 0).
        """
        for bone_key, buf in self._buffers.items():
            parent, child = self._endpoints[bone_key]
            p = positions.get(parent)
            c = positions.get(child)
            if p is None or c is None:
                continue
            length = float(np.linalg.norm(np.asarray(c, dtype=float) - np.asarray(p, dtype=float)))
            if errors is None:
                err = 0.0
            else:
                err = max(float(errors.get(parent, 0.0)), float(errors.get(child, 0.0)))
            buf.offer(length=length, error=err, t=t)

    @property
    def lengths(self) -> dict[str, float]:
        """Current best length estimate (mm) per bone."""
        return {bone_key: buf.estimate for bone_key, buf in self._buffers.items()}

    @property
    def seeds(self) -> dict[str, float]:
        """Current seed (mm) per bone: the anthropometric prior, or the captured
        calibration for bones that have been re-anchored via ``reseed``."""
        return {bone_key: buf.seed_length for bone_key, buf in self._buffers.items()}

    def agreed_medians(self) -> dict[str, float | None]:
        """Per-bone buffer consensus (mm), or None where no agreement yet."""
        return {bone_key: buf.agreed_median() for bone_key, buf in self._buffers.items()}

    def reseed(self, lengths: dict[str, float]) -> None:
        """Re-anchor the given bones on captured lengths.

        Raises ``KeyError`` on an unknown bone key — no partial reseeds.
        """
        for bone_key in lengths:
            if bone_key not in self._buffers:
                raise KeyError(f"Unknown bone '{bone_key}' — cannot reseed.")
        for bone_key, new_seed in lengths.items():
            self._buffers[bone_key].reseed(new_seed)

    def reset(self) -> None:
        """Forget every bone's measurements — all estimates fall back to their seeds."""
        for buf in self._buffers.values():
            buf.reset()
