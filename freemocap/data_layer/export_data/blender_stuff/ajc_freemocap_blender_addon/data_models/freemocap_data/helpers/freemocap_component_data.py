from dataclasses import dataclass
from typing import List

import numpy as np


@dataclass
class FreemocapComponentData:
    name: str
    data: np.ndarray
    data_source: str
    trajectory_names: List[str]
    data_dimensions: List[str] = None
    error: np.ndarray = None
    error_type: str = "mean_reprojection_error"

    def __post_init__(self):
        if isinstance(self.data, list):
            self.data = np.array(self.data)

        if isinstance(self.trajectory_names, str):
            self.trajectory_names = list(self.trajectory_names)

        if self.data.ndim == 3:
            self.data_dimensions = ["frame", "marker", "xyz"]
            if not self.data.shape[1] == len(self.trajectory_names):
                raise ValueError(
                    f"Data frame shape {self.data.shape} does not match trajectory names length {len(self.trajectory_names)}")

        elif self.data.ndim == 2:
            if not len(self.trajectory_names) == 1:
                raise ValueError(
                    f"Data frame shape {self.data.shape} does not match trajectory names length {len(self.trajectory_names)}")
            self.data_dimensions = ["frame", "xyz"]
