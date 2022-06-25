import logging
import threading
import time
import traceback
from typing import List

import numpy as np

from src.cameras.capture.dataclasses.frame_payload import FramePayload

logger = logging.getLogger(__name__)


class VideoCaptureThread(threading.Thread):
    def __init__(
            self,
            get_next_frame,
    ):
        super().__init__()
        self._is_capturing_frames = False
        self._is_recording_frames = False
        self._get_next_frame = get_next_frame
        self._num_frames_processed = 0
        self._elapsed_during_frame_grab = []
        self._timestamps_npy = []
        self._median_framerate = None
        self._frame: FramePayload = FramePayload()
        self._frame_list = []
        self.setDaemon(True)

    @property
    def median_framerate(self):
        if self._num_frames_processed == 0:
            logger.warning(f"No Frames processed yet, cannot calculate median_framerate")
        else:
            self._median_framerate = np.nanmedian((np.diff(self._timestamps_npy) ** -1) / 1e9)

        return self._median_framerate

    @property
    def latest_frame(self) -> FramePayload:
        return self._frame

    @property
    def frame_list(self) -> List:
        return self._frame_list

    @property
    def is_capturing_frames(self) -> bool:
        """Is the thread capturing frames from the cameras (but not necessarily recording them, that's handled by `is_recording_frames`)"""
        return self._is_capturing_frames

    @property
    def is_recording_frames(self) -> bool:
        """Is the thread *recording* the frames that are being capture from the camera (see also - `is_capturing_frames"""
        return self._is_recording_frames

    @is_recording_frames.setter
    def is_recording_frames(self, recording_frames_bool:bool):
        self._is_recording_frames = recording_frames_bool

    def stop(self):
        self._is_capturing_frames = False

    def run(self):
        self._start_frame_loop()

    def _start_frame_loop(self):
        self._is_capturing_frames = True

        try:
            while self._is_capturing_frames:

                start = time.perf_counter_ns()
                self._frame = self._get_next_frame()
                self._elapsed_during_frame_grab.append(time.perf_counter_ns() - start)
                self._timestamps_npy.append(self._frame.timestamp)
                self._num_frames_processed += 1
                if self.is_recording_frames:
                    self._frame_list.append(self._frame)
        except:
            logger.error("Frame loop thread exited due to error")
            traceback.print_exc()
        else:
            logger.info("Frame loop thread exited.")
