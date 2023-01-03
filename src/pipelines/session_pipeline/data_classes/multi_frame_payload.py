from typing import Dict, List, NamedTuple, Union

from old_src.cameras.capture.dataclasses.frame_payload import FramePayload


class MultiFramePayload(NamedTuple):
    frames_dict: Dict[str, FramePayload]
    multi_frame_number: int
    each_frame_timestamp: List[Union[int, float]]
    multi_frame_timestamp_seconds: Union[int, float]
