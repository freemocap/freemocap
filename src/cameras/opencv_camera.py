import logging
import math
import os
import platform
import threading
import time
from collections import deque
from pathlib import Path

import cv2
from pydantic import BaseModel, PrivateAttr

from src.cameras.dto import FramePayload

logger = logging.getLogger(__name__)

current_working_dir = os.getcwd()


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
    _num_frames_processed: int = PrivateAttr(0)
    _frame: FramePayload = PrivateAttr(None)
    _elapsed: float = PrivateAttr(0)
    _writer_location: str = PrivateAttr()

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

    def start_frame_capture(self, save_video=False):
        t = threading.Thread(
            target=self._start_frame_loop, daemon=True, args=(save_video,)
        )
        t.start()
        self._running_thread = t

    def stop_frame_capture(self):
        self._is_capturing_frames = False

    def latest_frame(self):
        if not self._frame:
            return False, None, None
        return self._frame

    def _prepare_writer(self):
        frame_width = int(self.opencv_video_capture_object.get(3))
        frame_height = int(self.opencv_video_capture_object.get(4))
        fps = int(self.opencv_video_capture_object.get(5))
        timestr = time.strftime("%Y%m%d_%H%M%S")
        p = Path().joinpath(current_working_dir, f"{timestr}.avi").resolve()
        return cv2.VideoWriter(
            "outfile.avi",
            cv2.VideoWriter_fourcc("M", "J", "P", "G"),
            # cv2.VideoWriter_fourcc('A', 'V', 'C', '1'),
            fps,
            (frame_width, frame_height),
        )

    def _start_frame_loop(self, save_video=False):
        self._is_capturing_frames = True
        start = time.time()
        writer = None
        if save_video:
            writer = self._prepare_writer()
        try:
            while self._is_capturing_frames:
                success, image, timestamp = self.get_next_frame()
                # will this slow us down?
                if save_video:
                    writer.write(image)
                self._frame = FramePayload(success, image, timestamp)
                self._last_100_frames.append((success, image, timestamp))
                self._num_frames_processed += 1
                self._elapsed = time.time() - start
        except:
            writer.release()

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

    def read_next_frame(self):
        return self.opencv_video_capture_object.read()

    def close(self):
        self.opencv_video_capture_object.release()
        logger.info("Closed camera {}".format(self.name))
