from typing import List

import numpy as np
from matplotlib import pyplot as plt

from src.cameras.persistence.video_writer.video_recorder import VideoRecorder


def save_synchronized_videos(list_of_video_recorders:List[VideoRecorder], calibration_videos:bool=False):
    each_cam_frame_list = []
    first_frame_timestamps = []
    final_frame_timestamps = []

    for video_recoder in list_of_video_recorders:
        cam_frame_list = video_recoder.frame_list
        # first_frame_timestamps.append(cam_frame_list[0].timestamp_in_seconds_from_record_start)
        # final_frame_timestamps.append(cam_frame_list[-1].timestamp_in_seconds_from_record_start)
        first_frame_timestamps.append(cam_frame_list[0].timestamp_unix_time_seconds)
        final_frame_timestamps.append(cam_frame_list[-1].timestamp_unix_time_seconds)
        each_cam_frame_list.append(cam_frame_list)

    latest_first_frame = np.max(first_frame_timestamps)
    earliest_final_frame = np.min(final_frame_timestamps)

    print(f"first_frame_timestamps: {first_frame_timestamps}")
    print(f"np.diff(first_frame_timestamps): {np.diff(first_frame_timestamps)}")
    print(f"latest_first_frame: {latest_first_frame}")

    print(f"final_frame_timestamps: {final_frame_timestamps}")
    print(f"np.diff(final_frame_timestamps): {np.diff(final_frame_timestamps)}")
    print(f"earliest_final_frame: {earliest_final_frame}")

    each_cam_clipped_frame_list = []
    each_cam_clipped_timestamp_list = []
    for og_frame_list in each_cam_frame_list:
        each_cam_clipped_frame_list.append([])
        each_cam_clipped_timestamp_list.append([])
        for frame in og_frame_list:
            if frame.timestamp_unix_time_seconds < latest_first_frame:
                continue
            if frame.timestamp_unix_time_seconds > earliest_final_frame:
                continue

            each_cam_clipped_frame_list[-1].append(frame)
            each_cam_clipped_timestamp_list[-1].append(frame.timestamp_unix_time_seconds)

    number_of_frames_per_camera = [len(f) for f in each_cam_clipped_frame_list]
    min_number_of_frames = np.min(number_of_frames_per_camera)
    print(f" (clipped) number_of_frames_per_camera: {number_of_frames_per_camera}, min:{min_number_of_frames}")

    each_cam_not_really_synchronized_frame_list = [frame_list[:min_number_of_frames] for frame_list in each_cam_clipped_frame_list]

    number_of_frames_per_camera = [len(f) for f in each_cam_not_really_synchronized_frame_list]
    print(f" (not_really_synchronized) number_of_frames_per_camera: {number_of_frames_per_camera}")

    final_frame_timestamps = [frame_list[-1].timestamp_unix_time_seconds for frame_list in each_cam_not_really_synchronized_frame_list]

    print(f"np.diff(final_frame_timestamps): {np.diff(final_frame_timestamps)}")

    for video_recoder, frame_list in  zip(list_of_video_recorders, each_cam_not_really_synchronized_frame_list):
        video_recoder.save_list_of_frames_to_video_file(list_of_frames=frame_list, calibration_videos=calibration_videos)




