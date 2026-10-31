"""Dense causal smoothing with elapsed-time prediction and owned output arrays."""
from dataclasses import dataclass
from collections.abc import Mapping
import numpy as np
from skellyforge.core.data_tensors.channel_values import ChannelValues

@dataclass(frozen=True, slots=True)
class FilteredKeypoints:
    positions: ChannelValues
    predicted_mask: np.ndarray
    retained_mask: np.ndarray | None = None

    @property
    def predicted_names(self):
        return frozenset(self.positions.names[index] for index in np.flatnonzero(self.predicted_mask))

    @property
    def observed_positions(self) -> ChannelValues:
        return self.positions.with_values(self.positions.data_values, self.positions.entry_present & ~self.predicted_mask)

    @property
    def sample_status(self) -> ChannelValues:
        status = self.positions.entry_present.astype(np.uint8)
        status[self.predicted_mask] = 2
        if self.retained_mask is not None:
            status[self.retained_mask] = 3
        return ChannelValues(self.positions.names, status, component_names=())

@dataclass
class RealtimeKeypointFilter:
    dims: int = 3
    min_cutoff: float = 1.0
    beta: float = 0.007
    d_cutoff: float = 1.0
    gap_duration_s: float = 0.3
    prediction_duration_s: float = 0.1
    velocity_half_life_s: float = 0.08
    smoothing_enabled: bool = True

    def __post_init__(self):
        self.component_names = tuple(f'component_{index}' for index in range(self.dims))
        self.reset()

    def _extend(self, names):
        if names == self._last_input_names:
            return
        self._last_input_names = names
        added = tuple(name for name in names if name not in self._columns)
        if not added:
            return
        self._names += added
        self._columns = {name: index for index, name in enumerate(self._names)}
        self._positions = np.concatenate((self._positions, np.full((len(added), self.dims), np.nan)))
        self._velocities = np.concatenate((self._velocities, np.zeros((len(added), self.dims))))
        self._times = np.concatenate((self._times, np.full(len(added), np.nan)))
        self._previous_present = np.concatenate((self._previous_present, np.zeros(len(added), bool)))
        # Allocate working arrays only when the declared entity layout grows.
        self._difference = np.empty_like(self._positions)
        self._factor = np.empty_like(self._positions)
        self._elapsed = np.empty(len(self._names))

    def filter(self, *, t: float, raw_keypoints: Mapping[str, np.ndarray]) -> FilteredKeypoints:
        points = raw_keypoints if isinstance(raw_keypoints, ChannelValues) else ChannelValues.from_mapping(raw_keypoints, component_names=self.component_names)
        if self._names and points.component_names != self.component_names:
            raise ValueError('Filter component identities must remain unchanged until reset')
        if points.data_values.shape[1:] != (self.dims,):
            raise ValueError('Filter components must match the declared dimension count')
        if not np.isfinite(t) or (self._last_t is not None and t <= self._last_t):
            raise ValueError('Filter timestamps must be finite and strictly increasing')
        self.component_names = points.component_names
        self._last_t = t
        self._extend(points.names)
        raw = points.aligned(self._names)
        present = points.aligned_presence(self._names) & np.isfinite(raw).all(axis=-1)
        initialized = np.isfinite(self._times)
        np.subtract(t, self._times, out=self._elapsed)
        fresh = present & (~initialized | (~self._previous_present & (self._elapsed > self.gap_duration_s)))
        active = present & ~fresh
        np.copyto(self._positions, raw, where=fresh[:, None])
        self._velocities[fresh] = 0.
        self._elapsed[~active] = 1.
        dt = self._elapsed[:, None]
        # Whole-array ufuncs retain reusable work storage; no per-point objects.
        np.subtract(raw, self._positions, out=self._difference, where=active[:, None])
        np.divide(self._difference, dt, out=self._difference, where=active[:, None])
        derivative_factor = 2*np.pi*self.d_cutoff*dt
        derivative_factor /= 1 + derivative_factor
        np.subtract(self._difference, self._velocities, out=self._difference, where=active[:, None])
        np.multiply(self._difference, derivative_factor, out=self._difference, where=active[:, None])
        np.add(self._velocities, self._difference, out=self._velocities, where=active[:, None])
        if self.smoothing_enabled:
            np.abs(self._velocities, out=self._factor)
            self._factor *= self.beta
            self._factor += self.min_cutoff
            self._factor *= 2*np.pi*dt
            self._factor /= self._factor + 1
            np.subtract(raw, self._positions, out=self._difference, where=active[:, None])
            np.multiply(self._difference, self._factor, out=self._difference, where=active[:, None])
            np.add(self._positions, self._difference, out=self._positions, where=active[:, None])
        else:
            np.copyto(self._positions, raw, where=present[:, None])
        self._times[present] = t
        np.subtract(t, self._times, out=self._elapsed)
        generated = ~present & initialized & (self._elapsed <= self.gap_duration_s + 1e-9) & (self.gap_duration_s > 0)
        held = generated & (self._elapsed > self.prediction_duration_s)
        # Integrate exponentially decaying velocity analytically. Prediction is
        # independent of how many missing frames have been processed.
        horizon = np.minimum(self._elapsed, self.prediction_duration_s)
        decay_rate = np.log(2.) / self.velocity_half_life_s
        travel_time = -np.expm1(-decay_rate * horizon) / decay_rate
        output = self._positions.copy()  # Publication owns its values across future calls.
        np.multiply(self._velocities, travel_time[:, None], out=self._difference, where=generated[:, None])
        np.add(output, self._difference, out=output, where=generated[:, None])
        available = present | generated
        output[~available] = np.nan
        np.copyto(self._previous_present, present)
        return FilteredKeypoints(ChannelValues(self._names, output, available, component_names=self.component_names), generated, held)

    def reset(self):
        self._last_input_names = None
        self._names = ()
        self._columns = {}
        self._positions = np.empty((0, self.dims), np.float64)
        self._velocities = np.empty_like(self._positions)
        self._times = np.empty(0, np.float64)
        self._previous_present = np.empty(0, bool)
        self._difference = np.empty_like(self._positions)
        self._factor = np.empty_like(self._positions)
        self._elapsed = np.empty(0)
        self._last_t = None
