from dataclasses import dataclass
from typing import List

import numpy as np


@dataclass
class RotationDataClass:
    rotation_matricies: List[np.ndarray]
    local_origin_fr_xyz: np.ndarray = np.array([0, 0, 0])
    x_hat_norm_fr_xyz: np.ndarray = np.array([1, 0, 0])
    y_hat_norm_fr_xyz: np.ndarray = np.array([0, 1, 0])
    z_hat_norm_fr_xyz: np.ndarray = np.array([0, 0, 1])