from dataclasses import dataclass
from typing import List

import numpy as np


@dataclass
class RotationDataClass:
    rotation_matricies: List[np.ndarray]
    local_origin_fr_xyz: np.ndarray = np.array([0, 0, 0])