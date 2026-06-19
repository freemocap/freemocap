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
    """One Euro filter applied per-keypoint with velocity-decay gap filling.

    Coordinate-space assumptions
    ----------------------------
    Input positions are in **millimeters** (triangulated from charuco-board
    calibration).  The One Euro cutoff formula is::

        cutoff(Hz) = min_cutoff + beta * |velocity(mm/s)|

    so **beta has units of 1/mm**.  Tuning beta for meter-space (e.g. 0.3)
    makes the filter ~1000× too responsive — effectively a near-pass-through
    for any non-zero velocity.  The defaults assume mm-space coordinates.
    """

    # Minimum cutoff frequency (Hz) when the keypoint is nearly stationary.
    #   adaptive cutoff(Hz) = min_cutoff + beta * |velocity_mm_s|
    # Variable framerate is handled via actual elapsed time — behaviour is the
    # same at 15 fps or 60 fps without any extra configuration.
    # 1.0 Hz → settles in ~0.4 s at 30 fps; raise if skeleton feels dragged.
    min_cutoff: float = 1.0
    # Speed coefficient (1/mm). Raises the cutoff in proportion to velocity (mm/s).
    # 0.007 → walking speed (500 mm/s) adds 3.5 Hz, making the filter snappy.
    # Keep in range 0.003–0.02 for mm-space data.
    # WARNING: beta = 0.3 (meter-space convention) is ~1000× too high for mm data.
    beta: float = 0.007
    # Cutoff for the velocity-estimate filter (Hz); 1.0 is a safe default.
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
            # TODO: Fix root cause — the aggregator is processing the same frame twice  causing      the filter to receive identical timestamps for consecutive frames. Until the data-flow bug is resolved, skip filtering this frame  to avoid crashing the pipeline.
            logger.error(
                f"Non-monotonic timestamp passed to keypoint filter: "
                f"t={t} <= last_t={self._last_t} (dt={t - self._last_t}). "
                f"The aggregator processed the same frame twice, or the clock went backwards. "
                f"Skipping filter for this frame."
            )
            return raw_keypoints
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
