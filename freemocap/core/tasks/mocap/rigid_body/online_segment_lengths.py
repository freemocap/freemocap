"""Rolling-window median bone-length estimation for the realtime rigidifier.

Each bone keeps a time-windowed buffer of its measured lengths (the last
``window_s`` seconds) and reports their **median** — the realtime analogue of the
posthoc pipeline's per-bone median over the whole recording (skellyforge
``enforce_rigid_bones``). Until a bone has any samples in its window (start-up, or
a bone that has been out of view longer than the window), it reports its
anthropometric seed (ratio × height) so the rigidifier always has a length to
enforce.

A plain rolling median — no trust region, no agreement gating, no error
weighting, no age decay. The median is inherently robust to the occasional
mis-triangulated frame, and lengths are measured only from really-observed
(non-extrapolated) endpoints, so a hidden limb contributes nothing.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np


@dataclass
class RollingBoneLengths:
    """Per-bone rolling-window median length estimator.

    ``update`` is called once per frame with the current canonical-named 3D
    positions of **real** (measured, not extrapolated) keypoints; ``lengths``
    returns the current median length estimate per bone for the rigidifier.

    Parameters
    ----------
    bone_seeds : dict[str, float]
        ``"parent->child" -> seed length (mm)`` (ratio × height). Defines which
        bones are tracked and the fallback length used while a bone's window is
        empty.
    window_s : float
        Rolling-window duration (seconds). A measurement is dropped once it is
        older than ``window_s`` relative to the most recent ``update`` timestamp.
    """

    bone_seeds: dict[str, float]
    window_s: float

    _endpoints: dict[str, tuple[str, str]] = field(default_factory=dict, init=False, repr=False)
    _windows: dict[str, deque[tuple[float, float]]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        for bone_key in self.bone_seeds:
            parent, child = bone_key.split("->", 1)
            self._endpoints[bone_key] = (parent, child)
            self._windows[bone_key] = deque()

    @property
    def endpoints(self) -> dict[str, tuple[str, str]]:
        """``"parent->child" -> (parent, child)`` for every tracked bone."""
        return dict(self._endpoints)

    @property
    def seeds(self) -> dict[str, float]:
        """Anthropometric seed (mm) per bone — the empty-window fallback."""
        return dict(self.bone_seeds)

    def update(self, positions: dict[str, np.ndarray], *, t: float) -> None:
        """Append this frame's per-bone length measurements, then age the windows.

        A bone is measured only when both endpoints are present. Every window —
        measured this frame or not — drops samples older than ``window_s`` so a
        bone that leaves view eventually falls back to its seed.
        """
        cutoff = t - self.window_s
        for bone_key, (parent, child) in self._endpoints.items():
            window = self._windows[bone_key]
            p = positions.get(parent)
            c = positions.get(child)
            if p is not None and c is not None:
                length = float(np.linalg.norm(np.asarray(c, dtype=float) - np.asarray(p, dtype=float)))
                if np.isfinite(length) and length > 0.0:
                    window.append((t, length))
            while window and window[0][0] < cutoff:
                window.popleft()

    @property
    def lengths(self) -> dict[str, float]:
        """Current median length estimate (mm) per bone, or the seed if empty."""
        out: dict[str, float] = {}
        for bone_key, window in self._windows.items():
            if window:
                out[bone_key] = float(np.median([length for _, length in window]))
            else:
                out[bone_key] = self.bone_seeds[bone_key]
        return out

    def reset(self) -> None:
        """Forget every bone's measurements — all estimates fall back to their seeds."""
        for window in self._windows.values():
            window.clear()
