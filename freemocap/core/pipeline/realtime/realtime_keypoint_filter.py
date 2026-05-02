"""
SimpleRealtimeKeypointFilter: lightweight One Euro filter wrapper for the realtime pipeline.

Applies per-keypoint One Euro smoothing to triangulated 3D positions and
predicts (extrapolates) positions for keypoints that temporarily disappear,
so the output stream doesn't blink when tracking is lost for a few frames.

Gap filling:
    When a keypoint is absent from raw_keypoints the filter calls predict()
    using its stored velocity, decaying that velocity each frame so the
    extrapolated point slows to a stop.  After max_prediction_frames
    consecutive misses the keypoint is dropped from the output entirely.

NaN handling:
    The One Euro filter has no NaN guards.  This is safe here because
    _merge_triangulated_arrays() in the aggregator already drops any
    NaN-containing triangulated points before they reach this filter —
    missing keypoints show up as absent dict keys, not NaN values.
"""

import logging
from dataclasses import dataclass, field

import numpy as np

from freemocap.core.tasks.mocap.skeleton_dewiggler.dewiggling_methods.one_euro_filter import OneEuroFilter3D

logger = logging.getLogger(__name__)


@dataclass
class SimpleRealtimeKeypointFilter:
    """One Euro filter applied per-keypoint with velocity-decay gap filling."""

    min_cutoff: float = 0.005
    beta: float = 0.3
    d_cutoff: float = 1.0
    max_prediction_frames: int = 3
    prediction_velocity_decay: float = 0.5

    _filters: dict[str, OneEuroFilter3D] = field(default_factory=dict, init=False, repr=False)
    _prediction_counts: dict[str, int] = field(default_factory=dict, init=False, repr=False)
    _last_t: float | None = field(default=None, init=False, repr=False)

    def filter(self, *, t: float, raw_keypoints: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        """Return smoothed + gap-filled keypoints.

        Args:
            t: Monotonic timestamp in seconds (must be strictly increasing across calls).
            raw_keypoints: Triangulated 3D positions, keyed by point name.
                           NaN-free — caller is responsible for pre-filtering.

        Returns:
            dict mapping point name → filtered (3,) ndarray.
            Includes predictions for recently-seen keypoints absent this frame.
        """
        if self._last_t is not None and t <= self._last_t:
            raise RuntimeError(
                f"Non-monotonic timestamp passed to keypoint filter: "
                f"t={t} <= last_t={self._last_t} (dt={t - self._last_t}). "
                f"The aggregator processed the same frame twice, or the clock went backwards."
            )
        self._last_t = t

        result: dict[str, np.ndarray] = {}

        # Process keypoints present this frame
        for name, pos in raw_keypoints.items():
            if name not in self._filters:
                self._filters[name] = OneEuroFilter3D(
                    t0=t,
                    x0=pos.astype(float),
                    min_cutoff=self.min_cutoff,
                    beta=self.beta,
                    d_cutoff=self.d_cutoff,
                )
                self._prediction_counts[name] = 0
                result[name] = pos
            else:
                self._prediction_counts[name] = 0
                result[name] = self._filters[name](t=t, x=pos.astype(float))

        # Predict keypoints absent this frame (gap filling)
        for name, filt in self._filters.items():
            if name in raw_keypoints:
                continue
            count = self._prediction_counts.get(name, 0)
            if count < self.max_prediction_frames:
                result[name] = filt.predict(t=t, velocity_decay=self.prediction_velocity_decay)
                self._prediction_counts[name] = count + 1

        return result

    def reset(self) -> None:
        """Clear all filter state. Call when the calibration/coordinate frame changes."""
        self._filters.clear()
        self._prediction_counts.clear()
        self._last_t = None
