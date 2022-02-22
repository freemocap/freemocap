import logging
import math
import platform
import threading
import time

import cv2
from pydantic import BaseModel, PrivateAttr
from collections import deque

logger = logging.getLogger(__name__)


class OpenCVCamera(BaseModel):
    """
    Performant implementation of video capture against webcams
    """

    webcam_id: int = 0
    name: str = f"Camera {webcam_id}"
    exposure: int = -6
    resolution_width: int = 800
    resolution_height: int = 600
    opencv_video_capture_object: cv2.VideoCapture = None

    _is_capturing_frames: bool = PrivateAttr(False)
    _running_thread = PrivateAttr(None)
    _last_100_frames: deque = PrivateAttr(deque(maxlen=100))
    _fps: float = PrivateAttr(0)
    _num_frames_processed: int = PrivateAttr(0)
    _frame: tuple = PrivateAttr(None)
    _elapsed: float = PrivateAttr(0)

    class Config:
        arbitrary_types_allowed = True

    @property
    def webcam_id_as_str(self):
        return str(self.webcam_id)

    @property
    def current_fps(self):
        if self._elapsed <= 0:
            return 0
        if self._num_frames_processed <= 0:
            return 0
        return int(math.ceil(self._num_frames_processed / self._elapsed))

    def connect(self):
        if platform.system() == "Windows":
            cap_backend = cv2.CAP_DSHOW
        else:
            cap_backend = cv2.CAP_ANY

        self.opencv_video_capture_object = cv2.VideoCapture(self.webcam_id, cap_backend)
        success, image = self.opencv_video_capture_object.read()

        if not success:
            logger.error(
                "Could not connect to a camera at port# {}".format(self.webcam_id)
            )
            return success

        # set camera stream parameters
        # self.opencv_video_capture_object.set(cv2.CAP_PROP_EXPOSURE, self.exposure)
        # self.opencv_video_capture_object.set(
        #     cv2.CAP_PROP_FRAME_WIDTH, self.resolution_width
        # )
        # self.opencv_video_capture_object.set(
        #     cv2.CAP_PROP_FRAME_HEIGHT, self.resolution_height
        # )

        self.opencv_video_capture_object.set(
            cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc("M", "J", "P", "G")
        )

        if success:
            logger.debug(f"Camera found at port number {self.webcam_id}")
            self.name = f"Camera {self.webcam_id}"
            fps_input_stream = int(self.opencv_video_capture_object.get(5))
            print("FPS of webcam hardware/input stream: {}".format(fps_input_stream))
            return success

    def start_frame_capture(self):
        t = threading.Thread(target=self._start_frame_loop, daemon=True)
        t.start()
        self._running_thread = t

    def stop_frame_capture(self):
        self._is_capturing_frames = False

    def latest_frame(self):
        if not self._frame:
            return False, None, None
        return self._frame

    def _start_frame_loop(self):
        self._is_capturing_frames = True
        start = time.time()
        while self._is_capturing_frames:
            success, image, timestamp = self.get_next_frame()
            self._frame = (success, image, timestamp)
            self._last_100_frames.append((success, image, timestamp))
            self._num_frames_processed += 1
            self._elapsed = time.time() - start

    def get_next_frame(self):
        timestamp_ns_pre_grab = time.time_ns()
        # Why grab not read? see ->
        # https://stackoverflow.com/questions/57716962/difference-between-video-capture-read-and
        # -grab
        grab_success = self.opencv_video_capture_object.grab()
        timestamp_ns_post_grab = time.time_ns()
        timestamp_ns = (timestamp_ns_pre_grab + timestamp_ns_post_grab) / 2

        if grab_success:
            success, image = self.opencv_video_capture_object.retrieve()
            # logger.info('{} successfully grabbed a frame at timestamp {}'.format(self.name,
            # timestamp_ns/1e9))
            return success, image, timestamp_ns

        return False, None, None

    def close(self):
        self.opencv_video_capture_object.release()
        logger.info("Closed camera {}".format(self.name))
