from typing import Dict, List

import numpy as np


class TimestampLogger:
    _num_frames_processed: int
    _start_time: float

    def __init__(self):
        self._num_frames_processed = 0
        self._timestamps = np.empty(0)

    def is_started(self):
        return self._num_frames_processed > 0

    @property
    def median_frames_per_second(self):
        if self._num_frames_processed <= 10:
            return 0
        return np.nanmedian(np.diff(self._timestamps)/1e9)**-1

    @property
    def number_of_frames(self):
        return self._num_frames_processed

    @property
    def timestamps(self):
        return self._timestamps

    @property
    def last_timestamp(self):
        if self._timestamps.shape[0] > 0:
            return self._timestamps[-1]
        return None

    def increment_frame_processed(self, timestamp):
        self._timestamps = np.append(self._timestamps, timestamp)
        self._num_frames_processed += 1


class TimestampManager:
    def __init__(self, webcam_ids: List[str]):
        self._webcam_ids = webcam_ids
        self._counters: Dict[str, TimestampLogger] = self._init_counters(webcam_ids)

    def _init_counters(self, webcam_ids: List[str]):
        d = {}
        for webcam_id in webcam_ids:
            d[webcam_id] = TimestampLogger()
        return d

    def get_timestamps_from_camera(self, webcam_id):
        return self._counters[webcam_id]

    def increment_frame_processed_for(self, webcam_id, timestamp):
        self._counters[webcam_id].increment_frame_processed(timestamp)

    def median_frames_per_second(self, webcam_id):
        return self._counters[webcam_id].median_frames_per_second


