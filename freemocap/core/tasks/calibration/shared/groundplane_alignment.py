"""Shared ground plane alignment for camera calibration.

Provides GroundPlaneResult, the output of ground plane estimation.

Used by both charuco-based and feet-based ground plane estimation.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass
class GroundPlaneResult:
    """Result of ground plane estimation from any method."""

    origin: NDArray[np.float64]  # (3,) world origin position
    rotation_matrix: NDArray[np.float64]  # (3,3) [x_hat | y_hat | z_hat]
    method: str  # "charuco" or "feet"

    def to_dict(self) -> dict:
        return {
            "origin": list(self.origin),
            "rotation_matrix": list(self.rotation_matrix),
            "method": self.method,
        }
