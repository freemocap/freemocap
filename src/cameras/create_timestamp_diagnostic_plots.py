import logging
from pathlib import Path
from typing import Union, Dict, List

import numpy as np

from src.cameras.capture.dataclasses.frame_payload import FramePayload

logger = logging.getLogger(__name__)


def gather_timestamps(list_of_frames: List[FramePayload]) -> np.ndarray:
    timestamps_npy = np.empty(0)

    for frame in list_of_frames:
        timestamps_npy = np.append(
            timestamps_npy, frame.timestamp_in_seconds_from_record_start
        )
    return timestamps_npy


def create_timestamp_diagnostic_plots(
    each_cam_synchronized_frame_list: List[List[FramePayload]],
    path_to_save_plots: Union[str, Path],
):
    """plot some diagnostics to assess quality of camera sync"""

    # opportunistic load of matplotlib to avoid startup time costs
    from matplotlib import pyplot as plt

    plt.set_loglevel("warning")

    each_cam_timestamps = []
    for cam_frame_list in each_cam_synchronized_frame_list:
        each_cam_timestamps.append(gather_timestamps(cam_frame_list))

    fig = plt.figure(figsize=(18, 10))
    max_frame_duration = 0.1
    ax1 = plt.subplot(
        131,
        title="Camera Frame Timestamp vs Frame#",
        xlabel="Frame#",
        ylabel="Timestamp (sec)",
    )
    ax2 = plt.subplot(
        132,
        ylim=(0, max_frame_duration),
        title="Camera Frame Duration Trace",
        xlabel="Frame#",
        ylabel="Duration (sec)",
    )
    ax3 = plt.subplot(
        133,
        xlim=(0, max_frame_duration),
        title="Camera Frame Duration Histogram (count)",
        xlabel="Duration(s, 1ms bins)",
        ylabel="Probability",
    )

    for camera_number, timestamps in enumerate(each_cam_timestamps):
        ax1.plot(timestamps, label=f"Camera# {str(camera_number)}")
        ax1.legend()
        ax2.plot(np.diff(timestamps), ".")
        ax3.hist(
            np.diff(timestamps),
            bins=np.arange(0, max_frame_duration, 0.0025),
            alpha=0.5,
        )

    fig_save_path = Path(path_to_save_plots)
    plt.savefig(str(fig_save_path))
    logger.info(f"Saving diagnostic figure as png")
    # plt.show()
