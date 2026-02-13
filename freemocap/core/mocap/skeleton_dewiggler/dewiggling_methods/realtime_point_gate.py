"""
RealtimePointGate: velocity-based rejection of garbage 3D points.

Tracks per-landmark accepted positions across frames. If a point jumps
further than max_velocity * dt between frames, it is rejected (excluded
from the returned dict). Only accepted points update the stored position,
so a single garbage spike doesn't shift the reference and cause cascading
rejections.

A staleness timeout prevents permanent lockout: if a point has been
rejected for too many consecutive frames, the gate resets that point
and accepts the next observation unconditionally.
"""

import logging

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


class RealtimePointGate:
    """Rejects 3D points whose frame-to-frame velocity exceeds a threshold."""

    def __init__(
        self,
        *,
        max_velocity_m_per_s: float,
        max_rejected_streak: int,
    ) -> None:
        self._max_velocity = max_velocity_m_per_s
        self._max_rejected_streak = max_rejected_streak
        self._previous_positions: dict[str, NDArray[np.float64]] = {}
        self._previous_t: float | None = None
        self._rejected_streak: dict[str, int] = {}

    def gate(
        self,
        *,
        t: float,
        points: dict[str, NDArray[np.float64]],
    ) -> dict[str, NDArray[np.float64]]:
        """Return only points that pass the velocity check.

        Args:
            t: timestamp in seconds (must be strictly increasing).
            points: raw triangulated positions, mapping name -> (3,) array.

        Returns:
            Subset of points that passed the velocity gate.
        """
        if self._previous_t is None:
            # First frame — accept everything, store state
            self._previous_positions = {
                name: pos.copy() for name, pos in points.items()
            }
            self._previous_t = t
            self._rejected_streak = {name: 0 for name in points}
            return points

        dt = t - self._previous_t
        if dt <= 0.0:
            raise ValueError(
                f"Time must be strictly increasing: "
                f"prev={self._previous_t}, t={t}, dt={dt}"
            )

        accepted: dict[str, NDArray[np.float64]] = {}
        n_rejected = 0

        for name, pos in points.items():
            if name not in self._previous_positions:
                # Never-before-seen point — accept unconditionally
                accepted[name] = pos
                self._previous_positions[name] = pos.copy()
                self._rejected_streak[name] = 0
                continue

            streak = self._rejected_streak.get(name, 0)
            if streak >= self._max_rejected_streak:
                # Staleness timeout — accept unconditionally to prevent lockout
                accepted[name] = pos
                self._previous_positions[name] = pos.copy()
                self._rejected_streak[name] = 0
                continue

            distance = float(np.linalg.norm(pos - self._previous_positions[name]))
            velocity = distance / dt

            if velocity <= self._max_velocity:
                accepted[name] = pos
                self._previous_positions[name] = pos.copy()
                self._rejected_streak[name] = 0
            else:
                # Rejected — do NOT update previous position
                self._rejected_streak[name] = streak + 1
                n_rejected += 1


        self._previous_t = t
        return accepted

    def reset(self) -> None:
        """Clear all state. Call when calibration changes."""
        self._previous_positions.clear()
        self._previous_t = None
        self._rejected_streak.clear()
