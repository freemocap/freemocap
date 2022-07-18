import logging
import os
import traceback
from pathlib import Path
from typing import List, Union

import cv2
import numpy as np
import pandas as pd

from src.cameras.capture.dataclasses.frame_payload import FramePayload
from src.cameras.persistence.video_writer.save_options_dataclass import SaveOptions
from src.config.data_paths import freemocap_data_path
from src.config.home_dir import (
    get_session_folder_path,
    get_synchronized_videos_folder_path,
    get_calibration_videos_folder_path,
    get_mediapipe_annotated_videos_folder_path,
)
from rich.progress import Progress

logger = logging.getLogger(__name__)


class VideoRecorder:
    def __init__(
        self,
        video_name: str,
        image_width: int,
        image_height: int,
        session_id: str,
        fourcc: str = "MP4V",
        calibration_video_bool: bool = False,
        mediapipe_annotated_video_bool: bool = False,
    ):
        self._video_name = video_name
        self._image_width = image_width
        self._image_height = image_height
        self._fourcc = fourcc
        self._frame_payload_list: List[FramePayload] = []
        self._timestamps_npy = np.empty(0)
        self._cv2_video_writer = None

        # get yr paths straight
        self._session_id = session_id

        self._mediapipe_annotated_video_bool = mediapipe_annotated_video_bool

    @property
    def video_name(self):
        return self._video_name

    @property
    def video_folder_path(self):
        return self._video_folder_path

    @property
    def path_to_save_video_file(self):
        return self._path_to_save_video_file

    @property
    def frame_count(self):
        return len(self._frame_payload_list)

    @property
    def frame_list(self):
        return self._frame_payload_list

    def save_frame_payload_to_video_file(self, frame_payload: FramePayload):
        if self._cv2_video_writer is None:
            self._initialize_video_writer()

        self._cv2_video_writer.write(frame_payload.image)

    def close(self):
        self._cv2_video_writer.release()

    def append_frame_payload_to_list(self, frame_payload: FramePayload):
        self._frame_payload_list.append(frame_payload)

    def save_list_of_frames_to_video_file(
        self,
        list_of_frames: List[FramePayload] = None,
        frames_per_second: float = None,
        calibration_videos: bool = False,
    ):
        if list_of_frames is None:
            list_of_frames = self._frame_payload_list

        if len(list_of_frames) == 0:
            logging.error(f"No frames to save for camera: {self._video_name}")
            raise Exception

        if frames_per_second is None:
            self._timestamps_npy = self._gather_timestamps(list_of_frames)
            frames_per_second = np.nanmedian((np.diff(self._timestamps_npy) ** -1))

        self._initialize_video_writer(
            frames_per_second=frames_per_second, calibration_videos=calibration_videos
        )
        self._write_frame_list_to_video_file(list_of_frames)
        self._save_timestamps(self._timestamps_npy)

    def save_image_list_to_disk(
        self, image_list: List[np.ndarray], frames_per_second: float
    ):
        if len(image_list) == 0:
            logging.error(f"No frames to save for : {self._video_name}")
            return

        self._initialize_video_writer(frames_per_second=frames_per_second)
        self._write_image_list_to_video_file(image_list)

    def _initialize_video_writer(
        self,
        frames_per_second: Union[int, float] = None,
        calibration_videos: bool = False,
    ):

        video_file_name = self._video_name + ".mp4"

        if calibration_videos:
            self._video_folder_path = Path(
                get_calibration_videos_folder_path(self._session_id)
            )
        elif self._mediapipe_annotated_video_bool:
            self._video_folder_path = Path(
                get_mediapipe_annotated_videos_folder_path(self._session_id)
            )
        else:
            self._video_folder_path = Path(
                get_synchronized_videos_folder_path(self._session_id)
            )

        self._path_to_save_video_file = self._video_folder_path / video_file_name

        self._cv2_video_writer = cv2.VideoWriter(
            str(self.path_to_save_video_file),
            cv2.VideoWriter_fourcc(*self._fourcc),
            frames_per_second,
            (int(self._image_width), int(self._image_height)),
        )

    def _write_frame_list_to_video_file(self, list_of_frames: List[FramePayload]):
        try:
            for frame in list_of_frames:
                self._cv2_video_writer.write(frame.image)

        except Exception as e:
            logger.debug("Failed during save in video writer")
            traceback.print_exc()
            raise e
        finally:
            logger.info(f"Saved video to path: {self.path_to_save_video_file}")
            self._cv2_video_writer.release()

    def _write_image_list_to_video_file(self, image_list: List[np.ndarray]):
        try:
            for image in image_list:
                self._cv2_video_writer.write(image)

        except Exception as e:
            logger.error(
                f"Failed during save in video writer: {self.path_to_save_video_file}"
            )
            traceback.print_exc()
            raise e
        finally:
            logger.info(f"Saved video to path: {self.path_to_save_video_file}")
            self._cv2_video_writer.release()

    def _gather_timestamps(self, list_of_frames: List[FramePayload]) -> np.ndarray:
        timestamps_npy = np.empty(0)
        try:
            for frame in list_of_frames:
                timestamps_npy = np.append(
                    timestamps_npy, frame.timestamp_in_seconds_from_record_start
                )
        except:
            logger.error("Error gathering timestamps")

        return timestamps_npy

    def _save_timestamps(self, timestamps_npy: np.ndarray):
        timestamp_file_name_npy = self._video_name + "_timestamps_binary.npy"
        timestamp_npy_full_save_path = self._video_folder_path / timestamp_file_name_npy
        np.save(str(timestamp_npy_full_save_path), timestamps_npy)
        logger.info(f"Saved timestamps to path: {timestamp_file_name_npy}")

        timestamp_file_name_csv = self._video_name + "_timestamps_human_readable.csv"
        timestamp_csv_full_save_path = self._video_folder_path / timestamp_file_name_csv
        timestamp_dataframe = pd.DataFrame(timestamps_npy)
        timestamp_dataframe.to_csv(str(timestamp_csv_full_save_path))
        logger.info(f"Saved timestamps to path: {timestamp_file_name_csv}")
