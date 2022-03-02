import logging
import platform
import time

import cv2
from pydantic import BaseModel

from src.cameras.dto import FramePayload
from src.cameras.frame_grabber import FrameThread
from src.cameras.open_cv_cam_writer import OpenCVCamWriter

logger = logging.getLogger(__name__)


class WebcamConfig(BaseModel):
    webcam_id: int = 0
    exposure: int = -6
    resolution_width: int = 800
    resolution_height: int = 600
    save_video: bool = True


class OpenCVCamera:
    """
    Performant implementation of video capture against webcams
    """

    _opencv_video_capture_object: cv2.VideoCapture = None
    _running_thread: FrameThread = None

    def __init__(self, config: WebcamConfig):
        self._config = config
        self._name = f"Camera {self._config.webcam_id}"

    @property
    def webcam_id_as_str(self):
        return str(self._config.webcam_id)

    @property
    def current_fps(self):
        return self._running_thread.current_fps

    @property
    def is_capturing_frames(self):
        if not self._running_thread:
            logger.error("Frame Capture thread not running yet")
            return False

        return self._running_thread.is_capturing_frames

    @property
    def current_fps_short(self) -> str:
        return "{:.2f}".format(self._running_thread.current_fps)

    def connect(self):
        if platform.system() == "Windows":
            cap_backend = cv2.CAP_DSHOW
        else:
            cap_backend = cv2.CAP_ANY

        self._opencv_video_capture_object = cv2.VideoCapture(
            self._config.webcam_id, cap_backend
        )
        success, image = self._opencv_video_capture_object.read()

        if not success:
            logger.error(
                "Could not connect to a camera at port# {}".format(
                    self._config.webcam_id
                )
            )
            return success

        # set camera stream parameters
        # self.opencv_video_capture_object.set(cv2.CAP_PROP_EXPOSURE, self._config.exposure)
        # self.opencv_video_capture_object.set(
        #     cv2.CAP_PROP_FRAME_WIDTH, self._config.resolution_width
        # )
        # self.opencv_video_capture_object.set(
        #     cv2.CAP_PROP_FRAME_HEIGHT, self._config.resolution_height
        # )

        self._opencv_video_capture_object.set(
            cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc("M", "J", "P", "G")
        )

        if success:
            logger.debug(f"Camera found at port number {self._config.webcam_id}")
            fps_input_stream = int(self._opencv_video_capture_object.get(5))
            print("FPS of webcam hardware/input stream: {}".format(fps_input_stream))
            return success

    def start_frame_capture(self):
        if self.is_capturing_frames:
            logger.debug(
                f"Already capturing frames for webcam_id: {self.webcam_id_as_str}"
            )
            return
        logger.info(
            f"Beginning frame capture thread for webcam: {self.webcam_id_as_str}"
        )
        self._running_thread = self._create_thread()
        self._running_thread.start()

    def _create_thread(self):
        return FrameThread(
            get_next_frame=self.get_next_frame,
            writer=OpenCVCamWriter().create_writer(self._opencv_video_capture_object),
            save_video=self._config.save_video,
        )

    @property
    def latest_frame(self):
        return self._running_thread.latest_frame

    def get_next_frame(self):
        timestamp_ns_pre_grab = time.time_ns()
        # Why grab not read? see ->
        # https://stackoverflow.com/questions/57716962/difference-between-video-capture-read-and
        # -grab
        grab_success = self._opencv_video_capture_object.grab()
        timestamp_ns_post_grab = time.time_ns()
        timestamp_ns = (timestamp_ns_pre_grab + timestamp_ns_post_grab) / 2

        if grab_success:
            success, image = self._opencv_video_capture_object.retrieve()
            return FramePayload(success, image, timestamp_ns)

        return FramePayload(False, None, None)

    def stop_frame_capture(self):
        self.close()

    def close(self):
        self._running_thread.stop()
        while self._running_thread.is_alive():
            # wait for thread to die.
            # TODO: use threading.Event for synchronize mainthread vs other threads
            time.sleep(0.1)
        self._opencv_video_capture_object.release()
        logger.info("Closed {}".format(self._name))
