import logging
from pathlib import Path
from typing import Dict, List, Union

import numpy as np
from matplotlib import pyplot as plt


from src.config.home_dir import get_session_folder_path

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
                 session_id:str,
                 webcam_ids: List[str],
                 session_start_time_unix_ns: int,
                 _session_start_time_perf_counter_ns:int):
        self._session_id = session_id
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
    def webcam_timestamp_loggers(self):
        return self._webcam_timestamp_loggers
    @property
    def number_of_cameras(self):
        return len(self._webcam_timestamp_loggers)

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

    def create_diagnostic_plots(self):
        """plot some diagnostics to assess quality of camera sync"""

        multi_frame_timestamp_list = self.multi_frame_timestamp_logger.timestamps_in_seconds_from_session_start
        multi_frame_interval_list = self.multi_frame_interval_list

        plt.ion()
        fig = plt.figure(figsize=(18, 10))
        max_frame_duration = 0.1
        ax1 = plt.subplot(
            231,
            title="Camera Frame Timestamp vs Frame#",
            xlabel="Frame#",
            ylabel="Timestamp (sec)",
        )
        ax2 = plt.subplot(
            232,
            ylim=(0, max_frame_duration),
            title="Camera Frame Duration Trace",
            xlabel="Frame#",
            ylabel="Duration (sec)",
        )
        ax3 = plt.subplot(
            233,
            xlim=(0, max_frame_duration),
            title="Camera Frame Duration Histogram (count)",
            xlabel="Duration(s, 1ms bins)",
            ylabel="Probability",
        )
        ax4 = plt.subplot(
            234,
            title="MuliFrame Timestamp vs Frame#",
            xlabel="Frame#",
            ylabel="Timestamp (sec)",
        )
        ax5 = plt.subplot(
            235,
            ylim=(0, max_frame_duration),
            title="Multi Frame Duration/Span Trace",
            xlabel="Frame#",
            ylabel="Duration (sec)",
        )
        ax6 = plt.subplot(
            236,
            xlim=(0, max_frame_duration),
            title="MultiFrame Duration Histogram (count)",
            xlabel="Duration(s, 1ms bins)",
            ylabel="Probability",
        )

        for this_camera_id, this_camera_timestamp_logger in self.webcam_timestamp_loggers.items():
            this_camera_timestamps = this_camera_timestamp_logger.timestamps_in_seconds_from_session_start
            ax1.plot(this_camera_timestamps, label=f"Camera# {this_camera_id}")
            ax1.legend()
            ax2.plot(np.diff(this_camera_timestamps), ".")
            ax3.hist(
                np.diff(this_camera_timestamps),
                bins=np.arange(0, max_frame_duration, 0.0025),
                alpha=0.5,
            )

        ax4.plot(
            multi_frame_timestamp_list,
            color="darkslategrey",
            label=f"MultiFrame"
        )
        ax5.plot(
            np.diff(multi_frame_timestamp_list),
            ".",
            color="darkslategrey",
            label="Multi Frame Duration",
        )
        ax5.plot(
            multi_frame_interval_list, ".", color="orangered", label="Frame TimeSpan"
        )
        ax5.legend()
        ax6.hist(
            np.diff(multi_frame_timestamp_list),
            bins=np.arange(0, max_frame_duration, 0.0025),
            density=True,
            alpha=0.5,
            color="darkslategrey",
            label="Frame Duration",
        )
        ax6.hist(
            np.diff(multi_frame_interval_list),
            bins=np.arange(0, max_frame_duration, 0.0025),
            density=True,
            alpha=0.5,
            color="orangered",
            label="Frame Timespan",
        )
        ax5.legend()

        fig_save_path = Path(get_session_folder_path(self._session_id)) / "camera_timestamp_diagnostics.png"
        plt.savefig(str(fig_save_path))
        logger.info(f"Saving diagnostic figure to - {str(fig_save_path)}")
        plt.show()