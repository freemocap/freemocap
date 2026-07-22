from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(slots=True, frozen=True)
class AngulationResult:
    """Output of `CalibrationStateTracker.try_angulate(...)` for one frame.

    points : dict[str, (3,) ndarray]
        Triangulated 3D point positions (mm), keyed by canonical point name.
        NaN-free — points that failed triangulation or the reprojection gate
        are absent, never NaN.
    errors_px : dict[str, float] | None
        Per-point mean reprojection error across cameras (px), keyed by the
        same names as ``points``. None when no error information exists —
        the single-camera planar-projection path, where reprojection error
        is undefined by construction.

    Hot path - slots removes per-instance __dict__ overhead, frozen makes it
    immutable so it can be shared across threads/queues without copying.
    """

    points: dict[str, NDArray[np.float64]]
    errors_px: dict[str, float] | None
