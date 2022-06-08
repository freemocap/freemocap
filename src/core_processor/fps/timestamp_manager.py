import logging
from typing import Dict, List, Union

import numpy as np

logger = logging.getLogger(__name__)


class TimestampLogger:
    _num_frames_processed: int
    _start_time: float

    def __init__(self, _session_start_time_perf_counter_ns: int):
        self._session_start_time_perf_counter_ns = _session_start_time_perf_counter_ns
        self._num_frames_processed = 0
        self._timestamps_ns = np.empty(0)

    def is_started(self):
        return self._num_frames_processed > 0

    @property
    def median_frames_per_second(self):
        if self._num_frames_processed <= 10:
            return 0
        return np.nanmedian(np.diff(self._timestamps_ns) / 1e9) ** -1

    @property
    def number_of_frames(self):
        return self._num_frames_processed

    @property
    def timestamps_unix_ns(self):
        """return timestamps in nanoseconds in Unix epoch format (which is both the most useful, ugliest, AND funniest time format around. You can use `self.timestamps_in_seconds_from_zero()` for a more intuitive time format"""
        return self._timestamps_ns - self._session_start_time_perf_counter_ns

    @property
    def timestamps(self):
        return self.timestamps_in_seconds_from_session_start

    @property
    def timestamps_in_seconds_from_session_start(self):
        """timestamps in seconds counting up from zero (where zero is the start time of the recording session)"""
        return (self._timestamps_ns - self._session_start_time_perf_counter_ns) / 1e9

    @property
    def latest_timestamp(self):
        """returns timestamps in seconds from session start"""
        if self.timestamps.shape[0] > 0:
            return self.timestamps[-1]
        return None

    def log_new_timestamp_ns(self, timestamp):
        self._timestamps_ns = np.append(self._timestamps_ns, timestamp)
        self._num_frames_processed += 1


class TimestampManager:
    def __init__(self,
                 webcam_ids: List[str],
                 session_start_time_unix_ns: int,
                 _session_start_time_perf_counter_ns:int):
        self._session_start_time_unix_ns = session_start_time_unix_ns #time.time_ns(), UNIX epoch time, nanoseconds
        self._session_start_time_perf_counter_ns = _session_start_time_perf_counter_ns #time.perf_counter_ns, arbitrary timebase, nanoseconds - corresponds to self.session_start_time_ns
        self._webcam_ids = webcam_ids
        self._webcam_timestamp_loggers: Dict[str, TimestampLogger] = self._initialize_webcam_timestamp_loggers(
            webcam_ids)
        self._main_loop_timestamp_logger = TimestampLogger(self._session_start_time_perf_counter_ns)
        self._multi_frame_timestamp_logger = TimestampLogger(self._session_start_time_perf_counter_ns)
        self._multi_frame_timestamps_list = []
        self._multi_frame_interval_list = []

    @property
    def multi_frame_timestamp_logger(self):
        return self._multi_frame_timestamp_logger

    @property
    def multi_frame_timestamps_list(self):
        return self._multi_frame_timestamps_list

    @property
    def multi_frame_interval_list(self):
        return self._multi_frame_interval_list

    @property
    def latest_multi_frame_timestamp_list(self):
        return self._multi_frame_timestamps_list[-1]

    @property
    def latest_multi_frame_interval(self):
        return self._multi_frame_interval_list[-1]

    def _initialize_webcam_timestamp_loggers(self, webcam_ids: List[str]):
        dictionary_of_timestamp_logger_objects = {}
        for webcam_id in webcam_ids:
            dictionary_of_timestamp_logger_objects[webcam_id] = TimestampLogger(self._session_start_time_unix_ns)
        return dictionary_of_timestamp_logger_objects

    def get_timestamps_from_camera_in_seconds_from_session_start(self, webcam_id):
        return self._webcam_timestamp_loggers[webcam_id].timestamps_in_seconds_from_session_start

    def number_of_frames(self, webcam_id):
        return self._webcam_timestamp_loggers[webcam_id].number_of_frames

    def median_frames_per_second_for_main_loop(self):
        return self._main_loop_timestamp_logger.median_frames_per_second

    def median_frames_per_second_for_webcam(self, webcam_id):
        return self._webcam_timestamp_loggers[webcam_id].median_frames_per_second

    def log_new_timestamp_for_main_loop_ns(self, timestamp):
        self._main_loop_timestamp_logger.log_new_timestamp_ns(timestamp)

    def log_new_multi_frame_timestamp_ns(self, timestamp):
        self._multi_frame_timestamp_logger.log_new_timestamp_ns(timestamp)

    def log_new_timestamp_for_webcam_ns(self, webcam_id: str, timestamp: Union[float, int],
                                        frame_number: int = None):
        self._webcam_timestamp_loggers[webcam_id].log_new_timestamp_ns(timestamp)
        if frame_number is not None:
            assert (self._webcam_timestamp_loggers[webcam_id].number_of_frames == frame_number,
                    f"Numer of timestamps ({self._webcam_timestamp_loggers[webcam_id].number_of_frames}) logged does not match frame_number ({frame_number})  for: camera_{webcam_id}")

    def _get_each_frame_timestamp(self, this_multi_frame_dict) -> List:

        this_multi_frame_timestamps = []
        for this_cam_id, this_cam_frame in this_multi_frame_dict.items():
            this_multi_frame_timestamps.append(this_cam_frame.timestamp)
        return this_multi_frame_timestamps

    def _get_intra_frame_interval_in_sec(self, this_multi_frame_timestamps) -> float:
        timestamp_min = np.min(this_multi_frame_timestamps)
        timestamp_max = np.max(this_multi_frame_timestamps)
        return (timestamp_max - timestamp_min) / 1e9

    def verify_multi_frame_is_synchronized(self,
                                           this_multi_frame_dict,
                                           expected_framerate: Union[int, None]) -> bool:

        this_multi_frame_timestamps = self._get_each_frame_timestamp(this_multi_frame_dict)
        this_multiframe_timestamp_interval_sec = self._get_intra_frame_interval_in_sec(this_multi_frame_timestamps)

        self._multi_frame_timestamps_list.append(this_multi_frame_timestamps)
        self._multi_frame_interval_list.append(this_multiframe_timestamp_interval_sec)

        if expected_framerate is None:
            logger.warning('`expected_framerate` not specified, Cannot verify multi_frame synchronization')
            return True

        if this_multiframe_timestamp_interval_sec > 2*(expected_framerate ** -1):
            return False

        return True
