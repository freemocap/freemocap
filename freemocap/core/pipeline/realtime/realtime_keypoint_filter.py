"""One Euro smoothing and gap prediction over dense entity/component arrays."""
import logging
from dataclasses import dataclass
from collections.abc import Mapping
import numpy as np
from skellyforge.core.data_tensors.channel_values import ChannelValues

logger = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True)
class FilteredKeypoints:
    positions: ChannelValues
    predicted_mask: np.ndarray

    @property
    def predicted_names(self):
        return frozenset(self.positions.names[index] for index in np.flatnonzero(self.predicted_mask))

@dataclass
class RealtimeKeypointFilter:
    dims: int = 3
    min_cutoff: float = 1.0
    beta: float = 0.007
    d_cutoff: float = 1.0
    max_prediction_frames: int = 3
    prediction_velocity_decay: float = 0.5

    def __post_init__(self) -> None:
        self.component_names = tuple(f"component_{index}" for index in range(self.dims))
        self.reset()

    def _extend(self, names: tuple[str, ...]) -> None:
        if names == self._last_input_names:
            return
        self._last_input_names = names
        added = tuple(name for name in names if name not in self._columns)
        if not added:
            return
        self._names += added
        self._columns = {name: i for i, name in enumerate(self._names)}
        self._positions = np.concatenate((self._positions, np.full((len(added), self.dims), np.nan)))
        self._velocities = np.concatenate((self._velocities, np.zeros((len(added), self.dims))))
        self._times = np.concatenate((self._times, np.full(len(added), np.nan)))
        self._counts = np.concatenate((self._counts, np.zeros(len(added), np.int64)))

    def filter(self, *, t: float, raw_keypoints: Mapping[str, np.ndarray]) -> FilteredKeypoints:
        points = raw_keypoints if isinstance(raw_keypoints, ChannelValues) else ChannelValues.from_mapping(raw_keypoints, component_names=self.component_names)
        if self._names and points.component_names != self.component_names:
            raise ValueError("Filter component identities must remain unchanged until reset")
        self.component_names = points.component_names
        if points.data_values.shape[1:] != (self.dims,):
            raise ValueError("Filter components must match the declared dimension count")
        if self._last_t is not None and t <= self._last_t:
            logger.warning("Non-monotonic timestamp: skipping filter for this frame")
            return FilteredKeypoints(points, np.zeros(len(points.names), bool))
        self._last_t = t
        self._extend(points.names)
        raw = points.aligned(self._names)
        present = points.aligned_presence(self._names)
        initialized = np.isfinite(self._times)
        fresh = present & ~initialized
        active = present & initialized
        self._positions[fresh] = raw[fresh]
        self._times[fresh] = t
        dt = (t - self._times[active])[:, None]
        derivative_factor = 2 * np.pi * self.d_cutoff * dt
        derivative_factor /= derivative_factor + 1
        derivative = (raw[active] - self._positions[active]) / dt
        velocity = derivative_factor * derivative + (1 - derivative_factor) * self._velocities[active]
        factor = 2 * np.pi * (self.min_cutoff + self.beta * np.abs(velocity)) * dt
        factor /= factor + 1
        self._positions[active] = factor * raw[active] + (1 - factor) * self._positions[active]
        self._velocities[active] = velocity
        self._times[active] = t
        self._counts[present] = 0
        predicted = ~present & initialized & (self._counts < self.max_prediction_frames)
        self._positions[predicted] += self._velocities[predicted] * (t - self._times[predicted])[:, None]
        self._velocities[predicted] *= self.prediction_velocity_decay
        self._times[predicted] = t
        self._counts[predicted] += 1
        available = present | predicted
        return FilteredKeypoints(ChannelValues(self._names, self._positions.copy(), available, component_names=self.component_names), predicted)

    def reset(self) -> None:
        self._last_input_names = None
        self._names: tuple[str, ...] = ()
        self._columns = {}
        self._positions = np.empty((0, self.dims), np.float64)
        self._velocities = np.empty_like(self._positions)
        self._times = np.empty(0, np.float64)
        self._counts = np.empty(0, np.int64)
        self._last_t = None
