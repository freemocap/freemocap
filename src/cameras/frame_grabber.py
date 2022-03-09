import logging
import threading
import time
import traceback

import cv2

from src.cameras.dto import FramePayload

logger = logging.getLogger(__name__)


class FrameThread(threading.Thread):
    def __init__(self, get_next_frame, writer: cv2.VideoWriter, save_video=False):
        super().__init__()
        self._save_video = save_video
        self._is_capturing_frames = False
        self._get_next_frame = get_next_frame
        self._num_frames_processed = 0
        self._elapsed = 0
        self._frame: FramePayload = FramePayload()
        self.setDaemon(True)
        if save_video:
            self._writer = writer

    @property
    def current_fps(self):
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
        self._start_frame_loop(self._save_video)

    def _start_frame_loop(self, save_video=False):
        self._is_capturing_frames = True
        start = time.time()
        try:
            while self._is_capturing_frames:
                success, image, timestamp = self._get_next_frame()
                if save_video:
                    self._writer.write(image)
                self._frame = FramePayload(success, image, timestamp)
                self._num_frames_processed += 1
                self._elapsed = time.time() - start
        except:
            logger.error("Frame loop thread exited due to error")
            traceback.print_exc()
        else:
            logger.info("Frame loop thread exited.")
        finally:
            self._writer.release()
