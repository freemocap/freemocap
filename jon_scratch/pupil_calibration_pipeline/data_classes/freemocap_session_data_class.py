from dataclasses import dataclass
from typing import List

import numpy as np

from jon_scratch.pupil_calibration_pipeline.data_classes.pupil_dataclass_and_handler import PupilData


@dataclass
class FreemocapSessionDataClass:
    session_id: str = None
    mediapipe_fr_mar_dim: np.ndarray = None
    right_eye_data: PupilData = None
    left_eye_data: PupilData = None
    head_rotation_matricies: List = None
    timestamps: np.ndarray = None

