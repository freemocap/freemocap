"""Velocity rejection with dense accepted positions and per-entity streaks."""
from dataclasses import dataclass
from collections.abc import Mapping
import numpy as np
from skellyforge.core.data_tensors.channel_values import ChannelValues, SPATIAL_COMPONENTS

@dataclass(frozen=True)
class GateResult:
    positions: ChannelValues
    held_mask: np.ndarray

    @property
    def held_names(self):
        return frozenset(self.positions.names[i] for i in np.flatnonzero(self.held_mask))

class RealtimePointGate:
    def __init__(self, *, max_velocity_mm_per_s: float, max_rejected_streak: int) -> None:
        self._max_velocity = max_velocity_mm_per_s
        self._max_rejected_streak = max_rejected_streak
        self.reset()

    def gate(self, *, t: float, points: Mapping[str, np.ndarray]) -> GateResult:
        points = ChannelValues.from_mapping(points, component_names=SPATIAL_COMPONENTS)
        if self._previous_t is not None and t <= self._previous_t:
            raise ValueError("Time must be strictly increasing")
        names = tuple(dict.fromkeys((*self._positions.names, *points.names)))
        previous = self._positions.aligned(names)
        raw = points.aligned(names)
        available = np.isfinite(raw).all(axis=-1)
        known = np.isfinite(previous).all(axis=-1)
        if len(names) != len(self._streaks):
            self._streaks = np.pad(self._streaks, (0, len(names) - len(self._streaks)))
        dt = t - self._previous_t if self._previous_t is not None else 1.
        held = available & known & (self._streaks < self._max_rejected_streak) & (np.linalg.norm(raw - previous, axis=-1) / dt > self._max_velocity)
        accepted = available & ~held
        previous[accepted] = raw[accepted]
        self._streaks[accepted] = 0
        self._streaks[held] += 1
        self._positions = ChannelValues(names, previous, known | available, component_names=SPATIAL_COMPONENTS)
        self._previous_t = t
        return GateResult(ChannelValues(names, previous.copy(), available, component_names=SPATIAL_COMPONENTS), held)

    def reset(self) -> None:
        self._positions = ChannelValues.empty(component_names=SPATIAL_COMPONENTS)
        self._streaks = np.empty(0, np.int64)
        self._previous_t = None
