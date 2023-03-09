from dataclasses import dataclass
from typing import Any

import numpy as np
from skellycam.detection.models.frame_payload import FramePayload

from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.mediapipe2d_numpy_arrays import \
    Mediapipe2dNumpyArrays


@dataclass
class Mediapipe2dDataPayload:
    raw_frame_payload: FramePayload = None
    mediapipe_results: Any = None
    annotated_image: np.ndarray = None
    pixel_data_numpy_arrays: Mediapipe2dNumpyArrays = None
