import logging
import multiprocessing
import platform
import threading
import time
import traceback
from multiprocessing import Process, Queue
from typing import Union

import cv2

from src.cameras.capture.dataclasses.frame_payload import FramePayload
from src.cameras.capture.opencv_camera.opencv_camera import OpenCVCamera
from src.cameras.detection.cam_singleton import get_or_create_cams
from src.config.webcam_config import WebcamConfig

logger = logging.getLogger(__name__)


class CvCamByProcess:

    def __init__(self, config: WebcamConfig = WebcamConfig()):
        self._process: Process = None
        self._recv, self._send = multiprocessing.Pipe(duplex=False)
        self._config = config
        self._is_capturing_frames = False
        self._new_frame_ready = False

    @property
    def webcam_id(self):
        return self._config.webcam_id

    @property
    def current_image(self) -> FramePayload:
        if self._is_capturing_frames:
            return self._recv.recv()
        return None

    def begin_frame_capture(self):
        if not self._is_capturing_frames:
            self._is_capturing_frames = True
            self._process = Process(
                target=self._start_frame_loop,
                args=(self._send,)
            )
            self._process.start()

    def end_frame_capture(self):
        self._is_capturing_frames = False
        self._process.kill()
        self._process = None

    def _create_obj(self, config: WebcamConfig):
        if platform.system() == "Windows":
            cap_backend = cv2.CAP_DSHOW
        else:
            cap_backend = cv2.CAP_ANY

        opencv_video_capture_object = cv2.VideoCapture(
            config.webcam_id, cap_backend
        )
        # self._apply_configuration()
        if not self._test_cap_connection(opencv_video_capture_object):
            raise Exception("Could not find camera")

        logger.debug(f"Camera found at port number {config.webcam_id}")
        fps_input_stream = int(opencv_video_capture_object.get(5))
        logger.debug(f"FPS of webcam hardware/input stream: {fps_input_stream}")
        return opencv_video_capture_object

    def _test_cap_connection(self, video_obj: cv2.VideoCapture):
        success, image = video_obj.read()

        if not success or image is None:
            logger.error(
                "Could not connect to a camera at port# {}".format(
                    self._config.webcam_id
                )
            )
            return False

        return True

    def _start_frame_loop(self, conn):
        video_cap = self._create_obj(self._config)
        try:
            while self._is_capturing_frames:
                payload = self._get_next_frame(video_cap)
                conn.send(payload)
        except:
            logger.error("Frame loop thread exited due to error")
            traceback.print_exc()
        else:
            logger.info("Frame loop exited.")

    def _get_next_frame(self, video_cap: cv2.VideoCapture):
        # Why `grab()` not `read()`? see ->
        # https://stackoverflow.com/questions/57716962/difference-between-video-capture-read-and
        # -grab
        if not video_cap.grab():
            return FramePayload(False, None, None)

        timestamp_ns_pre = time.perf_counter_ns()
        success, image = video_cap.retrieve()
        timestamp_ns_post = time.perf_counter_ns()

        timestamp_ns = (timestamp_ns_pre + timestamp_ns_post) / 2

        self._new_frame_ready = success

        return FramePayload(success=success,
                            image=image,
                            timestamp=timestamp_ns)





