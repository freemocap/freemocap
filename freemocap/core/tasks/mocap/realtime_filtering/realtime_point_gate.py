"""Reject motion outliers using time since each entity's last accepted input."""
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
        return frozenset(self.positions.names[index] for index in np.flatnonzero(self.held_mask))

class RealtimePointGate:
    def __init__(self, *, max_velocity_mm_per_s: float, reacquisition_timeout_s: float):
        self.configure(max_velocity_mm_per_s=max_velocity_mm_per_s, reacquisition_timeout_s=reacquisition_timeout_s)
        self.reset()

    def configure(self, *, max_velocity_mm_per_s: float, reacquisition_timeout_s: float):
        self._max_velocity = max_velocity_mm_per_s
        self._reacquisition_timeout = reacquisition_timeout_s

    def gate(self, *, t: float, points: Mapping[str, np.ndarray]) -> GateResult:
        points = ChannelValues.from_mapping(points, component_names=SPATIAL_COMPONENTS)
        if not np.isfinite(t) or (self._previous_t is not None and t <= self._previous_t):
            raise ValueError('Time must be finite and strictly increasing')
        if points.names != self._last_input_names:
            self._last_input_names = points.names
            names = tuple(dict.fromkeys((*self._positions.names, *points.names)))
            if names != self._positions.names:
                previous = self._positions.aligned(names)
                self._accepted_times = np.pad(self._accepted_times, (0, len(names)-len(self._accepted_times)), constant_values=np.nan)
                self._positions = ChannelValues(names, previous, np.isfinite(previous).all(axis=-1), component_names=SPATIAL_COMPONENTS)
                self._difference = np.empty_like(previous)
        names = self._positions.names
        raw = points.aligned(names)
        available = points.aligned_presence(names) & np.isfinite(raw).all(axis=-1)
        known = np.isfinite(self._accepted_times)
        elapsed = t - self._accepted_times
        np.subtract(raw, self._positions.data_values, out=self._difference)
        distance = np.linalg.norm(self._difference, axis=-1)
        held = available & known & (elapsed < self._reacquisition_timeout) & (distance > self._max_velocity * elapsed)
        accepted = available & ~held
        np.copyto(self._positions.data_values, raw, where=accepted[:, None])
        self._accepted_times[accepted] = t
        self._previous_t = t
        return GateResult(ChannelValues(names, self._positions.data_values.copy(), accepted, component_names=SPATIAL_COMPONENTS), held)

    def reset(self):
        self._positions = ChannelValues.empty(component_names=SPATIAL_COMPONENTS)
        self._accepted_times = np.empty(0)
        self._difference = np.empty((0, len(SPATIAL_COMPONENTS)))
        self._last_input_names = None
        self._previous_t = None
