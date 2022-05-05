from dataclasses import dataclass
from typing import List

import numpy as np

from jon_scratch.pupil_calibration_pipeline.data_classes.pupil_dataclass_and_handler import PupilData
from jon_scratch.pupil_calibration_pipeline.data_classes.rotation_data_class import RotationDataClass


@dataclass
class FreemocapSessionDataClass:
    session_id: str = None
    timestamps: np.ndarray = None
    mediapipe_skel_fr_mar_dim: np.ndarray = None
    right_eye_data: PupilData = None
    left_eye_data: PupilData = None
    head_rotation_data: RotationDataClass = None
    right_eye_socket_rotation_matricies: List = None
    left_eye_socket_rotation_matricies: List = None


