import logging
import os
import traceback
from pathlib import Path
from typing import List

import cv2
import numpy as np
import pandas as pd

from src.cameras.capture.dataclasses.frame_payload import FramePayload
from src.cameras.persistence.video_writer.save_options_dataclass import SaveOptions
from src.config.data_paths import freemocap_data_path

logger = logging.getLogger(__name__)


class VideoRecorder:
    def __init__(self,
                 camera_name: str,
                 image_width: int,
                 image_height: int,
                 fourcc: str = "MP4V"
                 ):
        self._camera_name = camera_name
        self._image_width = image_width
        self._image_height = image_height
        self._fourcc = fourcc
        self._frames: List[FramePayload] = []
        self._path_to_save_video = None
        self._video_type_str = ''
        self._timestamps_npy = np.array(0)

    @property
    def frame_count(self):
        return len(self._frames)

    def record(self, frame_payload: FramePayload):
        self._frames.append(frame_payload)

    def save_to_disk(self, path_to_save_video: Path, video_type_str: str = 'raw'):
        self._video_type_str = video_type_str
        self._path_to_save_video = path_to_save_video
        self._path_to_save_video.mkdir(parents=True, exist_ok=True)
        self._gather_timestamps()
        self._write_video()
        self._save_timestamps()

    def _write_video(self):
        video_file_name = self._camera_name + "_synchronized_" + self._video_type_str + ".mp4"
        video_full_path = self._path_to_save_video / video_file_name

        cv2_writer = cv2.VideoWriter(
            video_full_path,
            cv2.VideoWriter_fourcc(self._fourcc),
            self._median_framerate,
            (self._image_width, self._image_height))

        try:
            for frame in self._frames:
                cv2_writer.write(frame.image)

        except Exception as e:
            logger.debug("Failed during save in video writer")
            traceback.print_exc()
            raise e
        finally:
            logger.info(f"Saved video to path: {video_full_path}")
            cv2_writer.release()

    def _gather_timestamps(self):
        for frame in self._frames:
            self._timestamps_npy = np.append(self._timestamps_npy, frame.timestamp)
        self._median_framerate = np.median(np.diff(self._timestamps_npy))

    def _save_timestamps(self):
        timestamp_file_name_npy = self._camera_name + "_timestamps_ns.npy"
        np.save(str(self._path_to_save_video / timestamp_file_name_npy), self._timestamps_npy)
        logger.info(f"Saved timestamps to path: {timestamp_file_name_npy}")

        timestamp_file_name_csv = self._camera_name + "_timestamps_ns.csv"
        pd.DataFrame(self._timestamps_npy).to_csv(str(self._path_to_save_video / timestamp_file_name_csv))
        logger.info(f"Saved timestamps to path: {timestamp_file_name_csv}")