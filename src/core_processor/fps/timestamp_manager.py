from typing import Dict, List

import numpy as np


class TimestampLogger:
    _num_frames_processed: int
    _start_time: float

    def __init__(self, _session_start_time_unix_ns: int):
        self._session_start_time_unix_ns = _session_start_time_unix_ns
        self._num_frames_processed = 0
        self._timestamps = np.empty(0)

    def is_started(self):
        return self._num_frames_processed > 0

    @property
    def median_frames_per_second(self):
        if self._num_frames_processed <= 10:
            return 0
        return np.nanmedian(np.diff(self._timestamps) / 1e9) ** -1

    @property
    def number_of_frames(self):
        return self._num_frames_processed

    @property
    def timestamps(self):
        """return timestamps in nanoseconds in Unix epoch format (which is both the most useful, ugliest, AND funniest time format around. You can use `self.timestamps_in_seconds_from_zero()` for a more intuitive time format"""
        return self._timestamps

    @property
    def timestamps_in_seconds_from_session_start(self):
        """timestamps in seconds counting up from zero (where zero is the start time of the recording session)"""
        return (self._timestamps - self._session_start_time_unix_ns) / 1e9

    @property
    def last_timestamp(self):
        if self._timestamps.shape[0] > 0:
            return self._timestamps[-1]
        return None

    def log_new_timestamp(self, timestamp):
        self._timestamps = np.append(self._timestamps, timestamp)
        self._num_frames_processed += 1


class TimestampManager:
    def __init__(self, webcam_ids: List[str], session_start_time_unix_ns: int):
        self._session_start_time_unix_ns = session_start_time_unix_ns
        self._webcam_ids = webcam_ids
        self._webcam_timestamp_loggers: Dict[str, TimestampLogger] = self._initialize_timestamp_loggers(webcam_ids)
        self._main_loop_timestamp_logger = TimestampLogger(self._session_start_time_unix_ns)

    def _initialize_timestamp_loggers(self, webcam_ids: List[str]):
        dictionary_of_timestamp_logger_objects = {}
        for webcam_id in webcam_ids:
            dictionary_of_timestamp_logger_objects[webcam_id] = TimestampLogger(self._session_start_time_unix_ns)
        return dictionary_of_timestamp_logger_objects

    def get_timestamps_from_camera_in_seconds_from_session_start(self, webcam_id):
        return self._webcam_timestamp_loggers[webcam_id].timestamps_in_seconds_from_session_start

    def get_number_of_frames(self, webcam_id):
        return self._webcam_timestamp_loggers[webcam_id].number_of_frames

    def increment_main_loop_timestamp_logger(self, timestamp):
        self._main_loop_timestamp_logger.log_new_timestamp(timestamp)

    def median_frames_per_second_for_main_loop(self):
        return self._main_loop_timestamp_logger.median_frames_per_second

    def increment_frame_processed_for_webcam(self, webcam_id, timestamp):
        self._webcam_timestamp_loggers[webcam_id].log_new_timestamp(timestamp)

    def median_frames_per_second_for_webcam(self, webcam_id):
        return self._webcam_timestamp_loggers[webcam_id].median_frames_per_second
