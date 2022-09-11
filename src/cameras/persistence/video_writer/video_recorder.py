import logging
import os
import traceback
from pathlib import Path
from typing import List, Union

import cv2
import numpy as np
import pandas as pd

from src.cameras.capture.dataclasses.frame_payload import FramePayload


logger = logging.getLogger(__name__)


class VideoRecorder:
    def __init__(self):

        self._frame_payload_list: List[FramePayload] = []
        self._timestamps_npy = np.empty(0)

    @property
    def frame_count(self):
        return len(self._frame_payload_list)

    @property
    def frame_list(self):
        return self._frame_payload_list

    def close(self):
        self._cv2_video_writer.release()

    def append_frame_payload_to_list(self, frame_payload: FramePayload):
        self._frame_payload_list.append(frame_payload)

    def save_list_of_frames_to_video_file(
        self,
        list_of_frames: List[FramePayload],
        path_to_save_video_file: Union[str, Path],
        frames_per_second: float = None,
    ):

        if frames_per_second is None:
            self._timestamps_npy = self._gather_timestamps(list_of_frames)
            try:
                frames_per_second = np.nanmedian((np.diff(self._timestamps_npy) ** -1))
            except Exception as e:
                logger.debug("Error calculating frames per second")
                traceback.print_exc()
                raise e

        self._path_to_save_video_file = path_to_save_video_file

        self._cv2_video_writer = self._initialize_video_writer(
            image_height=list_of_frames[0].image.shape[0],
            image_width=list_of_frames[0].image.shape[1],
            frames_per_second=frames_per_second,
        )
        self._write_frame_list_to_video_file(list_of_frames)
        self._save_timestamps(timestamps_npy=self._timestamps_npy)
        self._cv2_video_writer.release()

    def save_image_list_to_disk(
        self,
        image_list: List[np.ndarray],
        path_to_save_video_file: Union[str, Path],
        frames_per_second: float,
    ):

        self._path_to_save_video_file = path_to_save_video_file

        if len(image_list) == 0:
            logging.error(f"No frames to save for : {self._path_to_save_video_file}")
            return

        self._cv2_video_writer = self._initialize_video_writer(
            image_height=image_list[0].shape[0],
            image_width=image_list[0].shape[1],
            frames_per_second=frames_per_second,
        )
        self._write_image_list_to_video_file(image_list)

    def _initialize_video_writer(
        self,
        image_height: Union[int, float],
        image_width: Union[int, float],
        frames_per_second: Union[int, float] = None,
        fourcc: str = "MP4V",
        # calibration_videos: bool = False,
    ) -> cv2.VideoWriter:

        video_writer_object = cv2.VideoWriter(
            str(self._path_to_save_video_file),
            cv2.VideoWriter_fourcc(*fourcc),
            frames_per_second,
            (int(image_width), int(image_height)),
        )

        if not video_writer_object.isOpened():
            logger.error(
                f"cv2.VideoWriter failed to initialize for: {str(self._path_to_save_video_file)}"
            )
            raise Exception

        return video_writer_object

    def _write_frame_list_to_video_file(self, list_of_frames: List[FramePayload]):
        try:
            for frame in list_of_frames:
                self._cv2_video_writer.write(frame.image)

        except Exception as e:
            logger.error(
                f"Failed during save in video writer for video {str(self._path_to_save_video_file)}"
            )
            traceback.print_exc()
            raise e
        finally:
            logger.info(f"Saved video to path: {self._path_to_save_video_file}")
            self._cv2_video_writer.release()

    def _write_image_list_to_video_file(self, image_list: List[np.ndarray]):
        try:
            for image in image_list:
                self._cv2_video_writer.write(image)
        except Exception as e:
            logger.error(
                f"Failed during save in video writer for video {str(self._path_to_save_video_file)}"
            )
            traceback.print_exc()
            raise e
        finally:
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
        timestamp_folder_path = self._path_to_save_video_file.parent / "timestamps"
        timestamp_folder_path.mkdir(parents=True, exist_ok=True)

        base_timestamp_path_str = str(
            timestamp_folder_path / self._path_to_save_video_file.stem
        )

        # save timestamps to npy (binary) file (via numpy.ndarray)
        path_to_save_timestamps_npy = base_timestamp_path_str + "_binary.npy"
        np.save(str(path_to_save_timestamps_npy), timestamps_npy)
        logger.info(f"Saved timestamps to path: {str(path_to_save_timestamps_npy)}")

        # save timestamps to human readable (csv/text) file (via pandas.DataFrame)
        path_to_save_timestamps_csv = (
            base_timestamp_path_str + "_timestamps_human_readable.csv"
        )
        timestamp_dataframe = pd.DataFrame(timestamps_npy)
        timestamp_dataframe.to_csv(str(path_to_save_timestamps_csv))
        logger.info(f"Saved timestamps to path: {str(path_to_save_timestamps_csv)}")
