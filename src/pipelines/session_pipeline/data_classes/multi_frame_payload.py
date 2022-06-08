from typing import NamedTuple, Union, Dict, List

import numpy as np

from src.cameras.capture.dataclasses.frame_payload import FramePayload


class MultiFramePayload(NamedTuple):
    frames_dict: Dict[str, FramePayload]
    multi_frame_number: int
    intra_frame_interval: Union[int, float]
    each_frame_timestamp: List[Union[int, float]]
    multi_frame_timestamp: Union[int, float]
