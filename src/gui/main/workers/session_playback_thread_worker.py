import time
from pathlib import Path
from typing import Union, Callable, List, Dict

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal, QTimer

from src.cameras.detection.cam_singleton import get_or_create_cams
from src.cameras.detection.models import FoundCamerasResponse

import logging

logger = logging.getLogger(__name__)


class SessionPlaybackThreadWorker(QThread):
    def __init__(
        self,
        frames_per_second: Union[int, float],
        list_of_video_paths: List[Union[str, Path]],
        dictionary_of_video_image_update_callbacks: Dict[str, Callable],
        skeleton_3d_npy: np.ndarray,
        update_3d_skeleton_callback: Callable,
    ):
        super().__init__()
        self._frame_duration = frames_per_second**-1
        self._list_of_video_paths = list_of_video_paths
        self._dictionary_of_video_image_update_callbacks = (
            dictionary_of_video_image_update_callbacks
        )

        self._skeleton_3d_frame_trackedPoint_dimension = skeleton_3d_npy
        self._update_3d_skeleton_callback = update_3d_skeleton_callback

        self._should_continue = True

    @property
    def should_continue(self):
        return self._should_continue

    @should_continue.setter
    def should_continue(self, set: bool):
        self._should_continue = set

    def _create_video_capture_dictionary(self):
        video_capture_object_dict = {}
        for video_path in self._list_of_video_paths:
            video_name = Path(video_path).stem
            video_capture_object_dict[video_name] = cv2.VideoCapture(str(video_path))

        return video_capture_object_dict

    def run(self):
        logger.info(
            f"Starting session_playback_thread_worker with frame_duration set to {self._frame_duration:.4f} seconds"
        )
        self._video_capture_object_dict = self._create_video_capture_dictionary()
        last_update_time = time.perf_counter()
        frame_number = -1
        reset_frame_number = False

        number_of_frames = list(self._video_capture_object_dict.values())[0].get(
            cv2.CAP_PROP_FRAME_COUNT
        )

        while self._should_continue:
            current_time = time.perf_counter()

            if current_time - last_update_time > self._frame_duration:
                last_update_time = current_time
                frame_number += 1
                if frame_number >= number_of_frames:
                    frame_number = 0

                reset_frame_number = True
                self._update_video_images(frame_number=frame_number)
                self._update_skeleton(frame_number=frame_number)

    def _update_video_images(self, frame_number: int):

        # update videos
        for (
            video_name,
            video_update,
        ) in self._dictionary_of_video_image_update_callbacks.items():
            if frame_number == 0:
                self._video_capture_object_dict[video_name].set(
                    cv2.CAP_PROP_POS_FRAMES, 0
                )
            success, image = self._video_capture_object_dict[video_name].read()
            if not success:
                logger.error(f"Failed to read a frame from video : {video_name}")
                raise Exception

            video_update(image)

    def _update_skeleton(self, frame_number: int):


        this_frame_skeleton_data = self._skeleton_3d_frame_trackedPoint_dimension[
            frame_number, :, :
        ]
        self._update_3d_skeleton_callback(this_frame_skeleton_data)
