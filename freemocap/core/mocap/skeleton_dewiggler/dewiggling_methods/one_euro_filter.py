"""
One Euro Filter for real-time signal smoothing.

Adaptive low-pass filter that adjusts its cutoff frequency based on
the speed of the signal. Slow movements get heavy smoothing (low cutoff),
fast movements get light smoothing (high cutoff, low lag).

Includes a `predict()` method for extrapolating position when observations
are temporarily missing. Prediction uses the stored filtered velocity,
decaying it each step so the extrapolation slows to a stop rather than
drifting forever. Internal state (t_prev, x_prev, dx_prev) is updated
during prediction so that when real observations resume, the filter
transitions smoothly.

Reference:
    Casiez, Roussel, Vogel (2012)
    "1€ Filter: A Simple Speed-based Low-pass Filter for Noisy Input in
     Interactive Systems"
    https://cristal.univ-lille.fr/~casiez/1euro/

Usage:
    filter_3d = OneEuroFilter3D(t0=0.0, x0=initial_position,
                                 min_cutoff=0.004, beta=0.7)
    for t, raw_pos in stream:
        if raw_pos is not None:
            smooth_pos = filter_3d(t=t, x=raw_pos)
        else:
            smooth_pos = filter_3d.predict(t=t, velocity_decay=0.75)
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

    def predict(self, *, t: float, velocity_decay: float) -> float:
        """Extrapolate position using the stored filtered velocity.

        Advances internal state so subsequent calls (real or predicted)
        see correct time deltas. Decays the velocity by ``velocity_decay``
        each call so predictions slow to a stop.

        Args:
            t: timestamp in seconds (must be strictly after t_prev).
            velocity_decay: multiplier applied to dx_prev after extrapolation.
                            0.0 = freeze immediately, 1.0 = constant velocity,
                            typical ~0.7-0.85 for graceful deceleration.

        Returns:
            Predicted position.
        """
        t_e = t - self.t_prev
        if t_e <= 0.0:
            raise ValueError(
                f"Time must be strictly increasing: "
                f"t_prev={self.t_prev}, t={t}, dt={t_e}"
            )

        x_predicted = self.x_prev + self.dx_prev * t_e

        self.x_prev = x_predicted
        self.dx_prev = self.dx_prev * velocity_decay
        self.t_prev = t
        return x_predicted


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

    def predict(self, *, t: float, velocity_decay: float) -> np.ndarray:
        """Extrapolate 3D position using stored filtered velocities.

        See OneEuroFilter1D.predict() for details on state advancement
        and velocity decay.

        Args:
            t: timestamp in seconds (must be strictly after t_prev).
            velocity_decay: per-axis velocity decay multiplier (0..1).

        Returns:
            Predicted (3,) position array.
        """
        return np.array([
            self._filters[i].predict(t=t, velocity_decay=velocity_decay)
            for i in range(3)
        ])
