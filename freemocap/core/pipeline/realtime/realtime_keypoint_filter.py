"""
RealtimeKeypointFilter: lightweight One Euro filter for the realtime pipeline.

Applies per-keypoint One Euro smoothing to 2D or 3D positions and predicts
(extrapolates) positions for keypoints that temporarily disappear, so the
output stream doesn't blink when tracking is lost for a few frames.

Works on ``dict[str, ndarray(dims,)]`` — set ``dims=2`` for pixel-space
(camera node) or ``dims=3`` for world-space (aggregator).
"""

import logging
from dataclasses import dataclass, field

import numpy as np

from freemocap.core.tasks.mocap.skeleton_dewiggler.dewiggling_methods.one_euro_filter import OneEuroFilter1D

logger = logging.getLogger(__name__)


@dataclass
class RealtimeKeypointFilter:
    """One Euro filter applied per-keypoint with velocity-decay gap filling.

    Works with 2D (pixel) or 3D (world) keypoints via the ``dims`` parameter.
    Each dimension gets an independent ``OneEuroFilter1D`` instance.
    """

    # Number of spatial dimensions (2 = pixel, 3 = world).
    dims: int = 3

    # Minimum cutoff frequency (Hz) when the keypoint is nearly stationary.
    min_cutoff: float = 1.0
    # Speed coefficient. For mm-space (~0.007); for pixel-space (~0.0001).
    beta: float = 0.007
    # Cutoff for the velocity-estimate filter (Hz).
    d_cutoff: float = 1.0

    max_prediction_frames: int = 3
    prediction_velocity_decay: float = 0.5

    # Per-keypoint state: each value is a tuple of ``dims`` OneEuroFilter1D
    # instances, one per spatial axis.
    _filters: dict[str, tuple[OneEuroFilter1D, ...]] = field(default_factory=dict, init=False, repr=False)
    _prediction_counts: dict[str, int] = field(default_factory=dict, init=False, repr=False)
    _last_t: float | None = field(default=None, init=False, repr=False)

    # ------------------------------------------------------------------
    def filter(
        self, *, t: float, raw_keypoints: dict[str, np.ndarray],
    ) -> dict[str, np.ndarray]:
        """Return smoothed + gap-filled keypoints.

        Args:
            t: Monotonic timestamp in seconds.
            raw_keypoints: Keypoints keyed by name. Each value is a
                           ``(dims,)`` ndarray. NaN-free — caller is
                           responsible for pre-filtering.

        Returns:
            dict mapping point name → filtered ``(dims,)`` ndarray.
            Includes predictions for recently-seen keypoints absent this frame.
        """
        if self._last_t is not None and t <= self._last_t:
            logger.warning(
                f"Non-monotonic timestamp: t={t} <= last_t={self._last_t}. "
                f"Skipping filter for this frame."
            )
            return raw_keypoints
        self._last_t = t

        result: dict[str, np.ndarray] = {}

        # Process keypoints present this frame.
        for name, pos in raw_keypoints.items():
            pos_f = pos.astype(float)
            if name not in self._filters:
                self._filters[name] = tuple(
                    OneEuroFilter1D(
                        t0=t, x0=float(pos_f[i]),
                        min_cutoff=self.min_cutoff,
                        beta=self.beta,
                        d_cutoff=self.d_cutoff,
                    )
                    for i in range(self.dims)
                )
                self._prediction_counts[name] = 0
                result[name] = pos_f
            else:
                self._prediction_counts[name] = 0
                result[name] = np.array([
                    self._filters[name][i](t=t, x=float(pos_f[i]))
                    for i in range(self.dims)
                ])

        # Predict keypoints absent this frame (gap filling).
        for name, filts in self._filters.items():
            if name in raw_keypoints:
                continue
            count = self._prediction_counts.get(name, 0)
            if count < self.max_prediction_frames:
                result[name] = np.array([
                    filts[i].predict(t=t, velocity_decay=self.prediction_velocity_decay)
                    for i in range(self.dims)
                ])
                self._prediction_counts[name] = count + 1

        return result

    def reset(self) -> None:
        """Clear all filter state (call on calibration / coordinate change)."""
        self._filters.clear()
        self._prediction_counts.clear()
        self._last_t = None
