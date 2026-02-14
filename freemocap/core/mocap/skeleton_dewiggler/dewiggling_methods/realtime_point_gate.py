"""
RealtimePointGate: velocity-based rejection of garbage 3D points.

Tracks per-landmark accepted positions across frames. If a point jumps
further than max_velocity * dt between frames, the last accepted position
is held (returned in place of the rejected observation). Only accepted
points update the stored reference position, so a single garbage spike
doesn't shift the reference and cause cascading rejections.

A staleness timeout prevents permanent lockout: if a point has been
rejected for too many consecutive frames, the gate resets that point
and accepts the next observation unconditionally.

The gate always returns positions for every input point — rejected points
get their last-accepted position substituted. The `held_names` field on
`GateResult` tells the caller which points are held vs. freshly accepted.
"""

import logging
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GateResult:
    """Result from the point gate: positions for all input points plus metadata."""

    # All points — accepted points have fresh positions, rejected points
    # have their last-accepted position substituted.
    positions: dict[str, NDArray[np.float64]]

    # Names of points whose positions are held (i.e. were rejected this frame).
    held_names: frozenset[str]


class RealtimePointGate:
    """Rejects 3D points whose frame-to-frame velocity exceeds a threshold.

    Rejected points are not dropped — instead, their last-accepted position
    is returned. This prevents blinking/flickering in the output.
    """

    def __init__(
        self,
        *,
        max_velocity_m_per_s: float,
        max_rejected_streak: int,
    ) -> None:
        self._max_velocity: float = max_velocity_m_per_s
        self._max_rejected_streak: int = max_rejected_streak
        self._accepted_positions: dict[str, NDArray[np.float64]] = {}
        self._previous_t: float | None = None
        self._rejected_streak: dict[str, int] = {}

    def gate(
        self,
        *,
        t: float,
        points: dict[str, NDArray[np.float64]],
    ) -> GateResult:
        """Return positions for all input points, holding last-accepted for rejected ones.

        Args:
            t: timestamp in seconds (must be strictly increasing).
            points: raw triangulated positions, mapping name -> (3,) array.

        Returns:
            GateResult with positions for every input point and the set of held names.
        """
        if self._previous_t is None:
            # First frame — accept everything, store state
            self._accepted_positions = {
                name: pos.copy() for name, pos in points.items()
            }
            self._previous_t = t
            self._rejected_streak = {name: 0 for name in points}
            return GateResult(
                positions=dict(points),
                held_names=frozenset(),
            )

        dt = t - self._previous_t
        if dt <= 0.0:
            raise ValueError(
                f"Time must be strictly increasing: "
                f"prev={self._previous_t}, t={t}, dt={dt}"
            )

        result_positions: dict[str, NDArray[np.float64]] = {}
        held: set[str] = set()

        for name, pos in points.items():
            if name not in self._accepted_positions:
                # Never-before-seen point — accept unconditionally
                result_positions[name] = pos
                self._accepted_positions[name] = pos.copy()
                self._rejected_streak[name] = 0
                continue

            streak = self._rejected_streak.get(name, 0)
            if streak >= self._max_rejected_streak:
                # Staleness timeout — accept unconditionally to prevent lockout
                result_positions[name] = pos
                self._accepted_positions[name] = pos.copy()
                self._rejected_streak[name] = 0
                continue

            distance = float(np.linalg.norm(pos - self._accepted_positions[name]))
            velocity = distance / dt

            if velocity <= self._max_velocity:
                result_positions[name] = pos
                self._accepted_positions[name] = pos.copy()
                self._rejected_streak[name] = 0
            else:
                # Rejected — return held position, do NOT update reference
                result_positions[name] = self._accepted_positions[name].copy()
                self._rejected_streak[name] = streak + 1
                held.add(name)

        self._previous_t = t
        return GateResult(
            positions=result_positions,
            held_names=frozenset(held),
        )

    def reset(self) -> None:
        """Clear all state. Call when calibration changes."""
        self._accepted_positions.clear()
        self._previous_t = None
        self._rejected_streak.clear()