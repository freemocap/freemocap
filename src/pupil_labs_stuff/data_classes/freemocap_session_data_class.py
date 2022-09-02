from dataclasses import dataclass
from typing import List

import numpy as np

from src.pupil_labs_stuff.data_classes.pupil_dataclass_and_handler import (
    PupilLabsDataClass,
)
from src.pupil_labs_stuff.data_classes.rotation_data_class import (
    RotationDataClass,
)


@dataclass
class FreemocapSessionDataClass:
    session_id: str = None
    timestamps: np.ndarray = None
    mediapipe_skel_fr_mar_dim: np.ndarray = None
    right_eye_pupil_labs_data: PupilLabsDataClass = None
    left_eye_pupil_labs_data: PupilLabsDataClass = None
    head_rotation_data: RotationDataClass = None
    right_eye_socket_rotation_data: RotationDataClass = None
    left_eye_socket_rotation_data: RotationDataClass = None
    right_gaze_vector_endpoint_fr_xyz: np.ndarray = None
    left_gaze_vector_endpoint_fr_xyz: np.ndarray = None
