import logging
from pathlib import Path
from typing import Dict, List, Union

import numpy as np
from old_src.cameras.capture.dataclasses.frame_payload import FramePayload
from old_src.cameras.persistence.video_writer.video_recorder import VideoRecorder
from old_src.config.home_dir import DIAGNOSTIC_PLOTS_FOLDER_NAME
from old_src.diagnostic_plot_makers.create_timestamp_diagnostic_plots import (
    create_timestamp_diagnostic_plots,
)

logger = logging.getLogger(__name__)


def save_synchronized_videos(
    dictionary_of_video_recorders: Dict[str, VideoRecorder],
    folder_to_save_videos=Union[str, Path],
):
    logger.info(f"saving synchronized video to folder: {str(folder_to_save_videos)}")

    each_cam_raw_frame_list = []
    first_frame_timestamps = []
    final_frame_timestamps = []

    for video_recoder in dictionary_of_video_recorders.values():
        cam_frame_list = video_recoder.frame_list
        # first_frame_timestamps.append(cam_frame_list[0].timestamp_in_seconds_from_record_start)
        # final_frame_timestamps.append(cam_frame_list[-1].timestamp_in_seconds_from_record_start)
        first_frame_timestamps.append(cam_frame_list[0].timestamp_unix_time_seconds)
        final_frame_timestamps.append(cam_frame_list[-1].timestamp_unix_time_seconds)
        each_cam_raw_frame_list.append(cam_frame_list)

    number_of_cameras = len(each_cam_raw_frame_list)

    latest_first_frame = np.max(first_frame_timestamps)
    earliest_final_frame = np.min(final_frame_timestamps)

    logger.info(f"first_frame_timestamps: {first_frame_timestamps}")
    logger.info(f"np.diff(first_frame_timestamps): {np.diff(first_frame_timestamps)}")
    logger.info(f"latest_first_frame: {latest_first_frame}")

    logger.info(f"final_frame_timestamps: {final_frame_timestamps}")
    logger.info(f"np.diff(final_frame_timestamps): {np.diff(final_frame_timestamps)}")
    logger.info(f"earliest_final_frame: {earliest_final_frame}")

    each_cam_clipped_frame_list = []
    each_cam_clipped_timestamp_list = []
    for og_frame_list in each_cam_raw_frame_list:
        each_cam_clipped_frame_list.append([])
        each_cam_clipped_timestamp_list.append([])
        for frame in og_frame_list:
            if frame.timestamp_unix_time_seconds < latest_first_frame:
                continue
            if frame.timestamp_unix_time_seconds > earliest_final_frame:
                continue

            each_cam_clipped_frame_list[-1].append(frame)
            each_cam_clipped_timestamp_list[-1].append(
                frame.timestamp_unix_time_seconds
            )

    number_of_frames_per_camera_clipped = [len(f) for f in each_cam_clipped_frame_list]
    min_number_of_frames = np.min(number_of_frames_per_camera_clipped)
    index_of_the_camera_with_fewest_frames = np.argmin(
        number_of_frames_per_camera_clipped
    )

    reference_frame_list = each_cam_clipped_frame_list[
        index_of_the_camera_with_fewest_frames
    ]
    number_of_frames_per_camera = len(reference_frame_list)

    each_cam_synchronized_frame_list = []
    for this_cam_number, this_cam_frame_list in enumerate(each_cam_clipped_frame_list):
        this_cam_synchronized_frame_list = []
        for this_reference_frame in reference_frame_list:
            closest_frame = get_nearest_frame(this_cam_frame_list, this_reference_frame)
            this_cam_synchronized_frame_list.append(closest_frame)
        each_cam_synchronized_frame_list.append(this_cam_synchronized_frame_list)

    logger.info(
        f" (clipped) number_of_frames_per_camera: {number_of_frames_per_camera_clipped}, min:{min_number_of_frames}"
    )

    final_frame_timestamps = [
        frame_list[-1].timestamp_unix_time_seconds
        for frame_list in each_cam_synchronized_frame_list
    ]

    logger.info(f"np.diff(final_frame_timestamps): {np.diff(final_frame_timestamps)}")

    for camera_id, video_recoder, frame_list in zip(
        dictionary_of_video_recorders.keys(),
        dictionary_of_video_recorders.values(),
        each_cam_synchronized_frame_list,
    ):
        video_recoder.save_list_of_frames_to_video_file(
            list_of_frames=frame_list,
            path_to_save_video_file=Path(folder_to_save_videos)
            / f"Camera_{str(camera_id).zfill(3)}.mp4",
        )

    diagnostic_plot_folder = Path(folder_to_save_videos) / DIAGNOSTIC_PLOTS_FOLDER_NAME
    diagnostic_plot_folder.mkdir(parents=True, exist_ok=True)
    path_to_save_plots = diagnostic_plot_folder / "timestamp_diagnostic_plots.png"
    create_timestamp_diagnostic_plots(
        each_cam_raw_frame_list,
        each_cam_synchronized_frame_list,
        path_to_save_plots,
    )


def get_nearest_frame(frame_list, reference_frame) -> FramePayload:
    timestamps = gather_timestamps(frame_list)

    close_frame_index = np.argmin(
        np.abs(timestamps - reference_frame.timestamp_unix_time_seconds)
    )

    return frame_list[close_frame_index]


def gather_timestamps(frame_list: List[FramePayload]) -> np.ndarray:
    timestamps_npy = np.empty(0)
    for frame in frame_list:
        timestamps_npy = np.append(timestamps_npy, frame.timestamp_unix_time_seconds)

    return timestamps_npy
