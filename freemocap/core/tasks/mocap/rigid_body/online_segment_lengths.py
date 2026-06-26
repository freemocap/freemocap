"""Streaming bone-length estimation for realtime rigid-body skeleton correction.

Each bone keeps a bounded "best-K" buffer of length measurements ranked by
reprojection error with an age decay, and reports their **median** — the realtime
analogue of the posthoc pipeline's per-bone median over the whole recording
(skellyforge ``enforce_rigid_bones.calculate_bone_lengths_and_statistics``).

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
        Anthropometric prior (mm) returned until ``min_samples`` real
        measurements have accumulated.
    min_samples : int
        Minimum buffered measurements before the median replaces the seed.
    max_error : float | None
        Reprojection-error gate: measurements above this are dropped outright.
    plausibility_tol : float | None
        Fractional deviation from the current buffer median above which a
        measurement is rejected as implausible (guards against low-error-but-
        wrong samples). Inactive until the buffer holds >= 2 samples.
    """

    capacity: int
    decay_tau_s: float
    seed_length: float
    min_samples: int = 1
    max_error: float | None = None
    plausibility_tol: float | None = None

    _samples: list[_Sample] = field(default_factory=list, init=False, repr=False)

    def offer(self, *, length: float, error: float, t: float) -> bool:
        """Offer one measurement. Returns True if it is retained in the buffer."""
        if not math.isfinite(length) or length <= 0.0:
            return False
        if self.max_error is not None and error > self.max_error:
            return False
        if self.plausibility_tol is not None and len(self._samples) >= 2:
            median = float(np.median([s.length for s in self._samples]))
            if median > 0.0 and abs(length - median) / median > self.plausibility_tol:
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

    @property
    def estimate(self) -> float:
        """Current best length estimate (mm): median of the buffer, else seed."""
        if len(self._samples) < self.min_samples:
            return self.seed_length
        return float(np.median([s.length for s in self._samples]))

    def __len__(self) -> int:
        return len(self._samples)

    def reset(self) -> None:
        """Forget all measurements — the estimate falls back to the seed."""
        self._samples.clear()


@dataclass
class OnlineBoneLengths:
    """One ``BoneLengthBuffer`` per bone, seeded from anthropometric ratios.

    ``update`` is called once per frame with the current canonical-named 3D
    positions and (optionally) per-keypoint reprojection errors; ``lengths``
    returns the current best length estimate per bone for the rigidifier.

    Parameters
    ----------
    bone_seeds : dict[str, float]
        ``"parent->child" -> seed length (mm)`` (ratio x height). Defines which
        bones are tracked and their starting estimates.
    capacity, decay_tau_s, min_samples, max_error, plausibility_tol
        Per-bone buffer settings (see ``BoneLengthBuffer``).
    """

    bone_seeds: dict[str, float]
    capacity: int
    decay_tau_s: float
    min_samples: int = 1
    max_error: float | None = None
    plausibility_tol: float | None = None

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
                min_samples=self.min_samples,
                max_error=self.max_error,
                plausibility_tol=self.plausibility_tol,
            )

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
        is only as trustworthy as its less-certain endpoint). When ``errors`` is
        None, measurements are treated as fully confident (error 0).
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

    def reset(self) -> None:
        """Forget every bone's measurements — all estimates fall back to their seeds."""
        for buf in self._buffers.values():
            buf.reset()
