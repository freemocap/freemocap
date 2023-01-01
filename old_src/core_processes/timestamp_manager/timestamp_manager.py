import logging
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)


class TimestampLogger:
    def __init__(
        self,
        logger_name: str,
        session_start_time_perf_counter_ns: int,
    ):
        self._logger_name = logger_name
        self._session_start_time_perf_counter_ns = session_start_time_perf_counter_ns
        self._num_frames_processed = 0
        self._timestamps_perf_counter_ns = np.empty(0)
        self._timestamps_from_zero = np.empty(0)

    @property
    def median_frames_per_second(self):
        if self._num_frames_processed <= 10:
            return 0
        return np.nanmedian(np.diff(self._timestamps_perf_counter_ns) / 1e9) ** -1

    @property
    def number_of_frames(self):
        return self._num_frames_processed

    @property
    def timestamps_in_seconds_from_session_start(self):
        """timestamps in seconds counting up from zero (where zero is the start time of the recording session)"""
        return (
            self._timestamps_perf_counter_ns - self._session_start_time_perf_counter_ns
        ) / 1e9

    @property
    def latest_timestamp_in_seconds_from_record_start(self):
        """returns timestamps in seconds from session start"""
        try:
            if self.timestamps_in_seconds_from_session_start.shape[0] > 0:
                return self.timestamps_in_seconds_from_session_start[-1]
        except:
            logger.error(f"Failed to return latest timestamp")

    def log_new_timestamp_perf_counter_ns(self, timestamp: int):
        self._timestamps_perf_counter_ns = np.append(
            self._timestamps_perf_counter_ns, timestamp
        )
        self._num_frames_processed += 1

    def log_new_timestamp_seconds_from_unspecified_zero(self, timestamp: float):
        self._timestamps_from_zero = np.append(self._timestamps_from_zero, timestamp)
        self._num_frames_processed += 1

    @property
    def timestamps_in_seconds_from_unspecified_zero(self):
        return self._timestamps_from_zero


class TimestampManager:
    def __init__(
        self,
        session_id: str,
        webcam_ids: List[str],
        session_start_time_unix_ns: int,
        _session_start_time_perf_counter_ns: int,
    ):

        self._session_id = session_id
        self._session_start_time_unix_ns = session_start_time_unix_ns
        self._session_start_time_perf_counter_ns = _session_start_time_perf_counter_ns

        self._webcam_ids = webcam_ids
        self._webcam_timestamp_loggers: Dict[
            str, TimestampLogger
        ] = self._initialize_webcam_timestamp_loggers(webcam_ids)
        self._main_loop_timestamp_logger = TimestampLogger(
            logger_name="main_loop",
            session_start_time_perf_counter_ns=self._session_start_time_perf_counter_ns,
        )

        self._multi_frame_timestamp_logger = TimestampLogger(
            logger_name="multi_frame",
            session_start_time_perf_counter_ns=self._session_start_time_perf_counter_ns,
        )

    def timestamp_logger_for_webcam_id(self, webcam_id: str) -> TimestampLogger:
        return self._webcam_timestamp_loggers[webcam_id]

    @property
    def multi_frame_timestamp_logger(self):
        return self._multi_frame_timestamp_logger

    def _initialize_webcam_timestamp_loggers(self, webcam_ids: List[str]):
        dictionary_of_timestamp_logger_objects = {}
        for webcam_id in webcam_ids:
            dictionary_of_timestamp_logger_objects[webcam_id] = TimestampLogger(
                logger_name="camera_" + webcam_id,
                session_start_time_perf_counter_ns=self._session_start_time_perf_counter_ns,
            )
        return dictionary_of_timestamp_logger_objects

    def _get_each_frame_timestamp(self, this_multi_frame_dict) -> List:
        this_multi_frame_timestamps = []
        for this_cam_id, this_cam_frame in this_multi_frame_dict.items():
            this_multi_frame_timestamps.append(
                this_cam_frame.timestamp_in_seconds_from_record_start
            )
        return this_multi_frame_timestamps

    def _get_intra_frame_interval_in_seconds(
        self, this_multi_frame_timestamps_in_seconds
    ) -> float:
        timestamp_min = np.min(this_multi_frame_timestamps_in_seconds)
        timestamp_max = np.max(this_multi_frame_timestamps_in_seconds)
        return timestamp_max - timestamp_min

    def verify_multi_frame_is_synchronized(
        self,
        this_multi_frame_dict,
    ) -> bool:

        this_multi_frame_timestamps = self._get_each_frame_timestamp(
            this_multi_frame_dict
        )
        this_multiframe_timestamp_interval_in_seconds = (
            self._get_intra_frame_interval_in_seconds(this_multi_frame_timestamps)
        )

        print(
            f"this_multiframe_timestamp_interval: {this_multiframe_timestamp_interval_in_seconds*1e3:.6f} milliseconds"
        )

        return True
