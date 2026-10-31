"""Repeatable disturbances on dense (time, entity, component) reference arrays."""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class TrajectoryPerturbations:
    noise_sigma: float = 0.0
    dropout_start_s: float = 1.0
    dropout_duration_s: float = 0.3
    complete_dropout: bool = False
    random_seed: int = 712

    def apply(self, *, timestamps_s: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        times = np.asarray(timestamps_s, dtype=np.float64)
        data = np.asarray(values)
        if data.ndim != 3 or times.shape != (len(data),) or not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
            raise ValueError('Expected increasing timestamps and time/entity/component arrays')
        if self.noise_sigma < 0 or self.dropout_duration_s < 0:
            raise ValueError('Noise and dropout duration must be nonnegative')
        result = data.astype(np.float64, copy=True)
        result += np.random.default_rng(self.random_seed).normal(0, self.noise_sigma, result.shape)
        affected = ((times - times[0]) >= self.dropout_start_s) & ((times - times[0]) < self.dropout_start_s + self.dropout_duration_s)
        hidden = np.zeros(data.shape[:-1], dtype=bool)
        hidden[affected, :] = True
        if not self.complete_dropout:
            hidden[:, 1:] = False
        result[hidden] = np.nan
        return result, hidden
