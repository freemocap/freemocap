import logging
import threading
import time
import traceback

from src.cameras.capture.dataclasses.frame_payload import FramePayload

logger = logging.getLogger(__name__)


class VideoCaptureThreadHandler(threading.Thread):
    def __init__(
            self,
            get_next_frame,
    ):
        super().__init__()
        self._is_capturing_frames = False
        self._get_next_frame = get_next_frame
        self._num_frames_processed = 0
        self._elapsed = 0
        self._frame: FramePayload = FramePayload()
        self.setDaemon(True)

    @property
    def average_fps(self):
        if self._elapsed <= 0:
            return 0
        if self._num_frames_processed <= 0:
            return 0
        return self._num_frames_processed / self._elapsed

    @property
    def latest_frame(self):
        return self._frame

    @property
    def is_capturing_frames(self):
        return self._is_capturing_frames

    def stop(self):
        self._is_capturing_frames = False

    def run(self):
        self._start_frame_loop()

    def _start_frame_loop(self, save_video=False):
        self._is_capturing_frames = True
        start = time.time()
        try:
            while self._is_capturing_frames:
                frame = self._get_next_frame()
                self._num_frames_processed += 1
                self._elapsed = time.time() - start
        except:
            logger.error("Frame loop thread exited due to error")
            traceback.print_exc()
        else:
            logger.info("Frame loop thread exited.")
