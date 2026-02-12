"""
One Euro Filter for real-time signal smoothing.

Adaptive low-pass filter that adjusts its cutoff frequency based on
the speed of the signal. Slow movements get heavy smoothing (low cutoff),
fast movements get light smoothing (high cutoff, low lag).

Reference:
    Casiez, Roussel, Vogel (2012)
    "1€ Filter: A Simple Speed-based Low-pass Filter for Noisy Input in
     Interactive Systems"
    https://cristal.univ-lille.fr/~casiez/1euro/

Usage:
    filter_3d = OneEuroFilter3D(t0=0.0, x0=initial_position,
                                 min_cutoff=0.004, beta=0.7)
    for t, raw_pos in stream:
        smooth_pos = filter_3d(t=t, x=raw_pos)
"""

import math

import numpy as np


def _smoothing_factor(t_e: float, cutoff: float) -> float:
    r = 2.0 * math.pi * cutoff * t_e
    return r / (r + 1.0)


def _exponential_smoothing(a: float, x: float, x_prev: float) -> float:
    return a * x + (1.0 - a) * x_prev


class OneEuroFilter1D:
    """One Euro low-pass filter for a single scalar signal."""

    __slots__ = ("min_cutoff", "beta", "d_cutoff", "x_prev", "dx_prev", "t_prev")

    def __init__(
        self,
        *,
        t0: float,
        x0: float,
        dx0: float = 0.0,
        min_cutoff: float = 1.0,
        beta: float = 0.0,
        d_cutoff: float = 1.0,
    ) -> None:
        self.min_cutoff: float = min_cutoff
        self.beta: float = beta
        self.d_cutoff: float = d_cutoff
        self.x_prev: float = x0
        self.dx_prev: float = dx0
        self.t_prev: float = t0

    def __call__(self, *, t: float, x: float) -> float:
        """Return filtered value. ``t`` must be strictly increasing."""
        t_e = t - self.t_prev
        if t_e <= 0.0:
            raise ValueError(
                f"Time must be strictly increasing: "
                f"t_prev={self.t_prev}, t={t}, dt={t_e}"
            )

        # Filtered derivative
        a_d = _smoothing_factor(t_e, self.d_cutoff)
        dx = (x - self.x_prev) / t_e
        dx_hat = _exponential_smoothing(a_d, dx, self.dx_prev)

        # Adaptive cutoff
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        a = _smoothing_factor(t_e, cutoff)
        x_hat = _exponential_smoothing(a, x, self.x_prev)

        self.x_prev = x_hat
        self.dx_prev = dx_hat
        self.t_prev = t
        return x_hat


class OneEuroFilter3D:
    """One Euro filter for a 3D point (filters x, y, z independently)."""

    __slots__ = ("_filters",)

    def __init__(
        self,
        *,
        t0: float,
        x0: np.ndarray,
        min_cutoff: float = 1.0,
        beta: float = 0.0,
        d_cutoff: float = 1.0,
    ) -> None:
        if x0.shape != (3,):
            raise ValueError(f"Expected shape (3,), got {x0.shape}")
        self._filters: tuple[OneEuroFilter1D, ...] = tuple(
            OneEuroFilter1D(
                t0=t0,
                x0=float(x0[i]),
                min_cutoff=min_cutoff,
                beta=beta,
                d_cutoff=d_cutoff,
            )
            for i in range(3)
        )

    def __call__(self, *, t: float, x: np.ndarray) -> np.ndarray:
        """Return filtered 3D position. ``t`` must be strictly increasing."""
        if x.shape != (3,):
            raise ValueError(f"Expected shape (3,), got {x.shape}")
        return np.array([
            self._filters[i](t=t, x=float(x[i]))
            for i in range(3)
        ])
